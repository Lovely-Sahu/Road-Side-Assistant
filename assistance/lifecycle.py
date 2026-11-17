"""
RSA Assistance Lifecycle Service
--------------------------------

The single, database-backed implementation of the assistance workflow:

    driver report -> AI analysis -> stored request -> provider assignment
    -> provider job state machine -> tracking -> completion / cancellation
    -> reassignment -> notifications -> escalation

Before this module the same workflow was implemented separately (and
inconsistently) in web.py, provider/jobs.py, provider/dashboard.py and
provider/requests.py: status updates were not validated everywhere, the request,
service match and tracking records were written by separate connections (a
crash left half-created requests), and nothing prevented a request from being
assigned twice.

Invariants enforced here:
- A request is stored (and committed) before any assignment is attempted, so an
  assignment failure can never lose the driver's report.
- Every multi-record change runs in ONE transaction (``database.transaction``).
- At most one active service match per request (checked here and enforced by a
  unique partial index from migration 1).
- ``assistance_requests.status`` always mirrors the active match status; when a
  provider rejects/fails, the request returns to REQUESTED and is re-matched
  excluding that provider.
- Provider status changes follow ``PROVIDER_TRANSITIONS``; repeated identical
  updates are idempotent; invalid ones raise ``LifecycleError`` (HTTP 409).
- Notifications are written only after the change has committed.
"""

import json
import logging
import os

from database.database import fetch_all, fetch_one, transaction, utc_now
from provider.provider import ACTIVE_JOB_STATUSES, haversine, rank_providers
from utils.validators import (
    ValidationError,
    clean_text,
    parse_coordinates,
    parse_optional_float,
)

from . import notifications


logger = logging.getLogger("rsa.lifecycle")


# ==========================================================
# STATUS MODEL
# ==========================================================

REQUEST_STATUSES = ("REQUESTED", "ASSIGNED", "ACCEPTED", "ON_THE_WAY", "ARRIVED",
                    "IN_PROGRESS", "COMPLETED", "CANCELLED")

ACTIVE_MATCH_STATUSES = ACTIVE_JOB_STATUSES  # ASSIGNED, ACCEPTED, ON_THE_WAY, ARRIVED, IN_PROGRESS
TERMINAL_MATCH_STATUSES = ("COMPLETED", "CANCELLED", "REJECTED", "UNABLE_TO_COMPLETE", "REASSIGNED")
OPEN_REQUEST_STATUSES = ("REQUESTED", "ASSIGNED", "ACCEPTED", "ON_THE_WAY", "ARRIVED", "IN_PROGRESS")

# Provider-driven job transitions (service_matches.status).
# ASSIGNED -> ON_THE_WAY is allowed directly (accepting implicitly), which is the
# transition that previously failed with "Cannot change job status from ASSIGNED
# to ON_THE_WAY".
PROVIDER_TRANSITIONS = {
    "ASSIGNED": ("ACCEPTED", "ON_THE_WAY", "REJECTED"),
    "ACCEPTED": ("ON_THE_WAY", "UNABLE_TO_COMPLETE"),
    "ON_THE_WAY": ("ARRIVED", "UNABLE_TO_COMPLETE"),
    "ARRIVED": ("IN_PROGRESS", "UNABLE_TO_COMPLETE"),
    "IN_PROGRESS": ("COMPLETED", "UNABLE_TO_COMPLETE"),
}

PROVIDER_STATUSES = {s for targets in PROVIDER_TRANSITIONS.values() for s in targets}

# Drivers may cancel until service work has started.
DRIVER_CANCELLABLE = ("REQUESTED", "ASSIGNED", "ACCEPTED", "ON_THE_WAY", "ARRIVED")
# Administrators may reassign until service work has started.
REASSIGNABLE = ("REQUESTED", "ASSIGNED", "ACCEPTED", "ON_THE_WAY", "ARRIVED")

# Location breadcrumbs are recorded only while the provider is travelling.
LOCATION_TRACKED_STATUSES = ("ACCEPTED", "ON_THE_WAY", "ARRIVED")

STATUS_LABELS = {
    "REQUESTED": "Waiting for a provider",
    "ASSIGNED": "Provider assigned",
    "ACCEPTED": "Accepted by provider",
    "ON_THE_WAY": "Provider on the way",
    "ARRIVED": "Provider arrived",
    "IN_PROGRESS": "Service in progress",
    "COMPLETED": "Completed",
    "CANCELLED": "Cancelled",
    "REJECTED": "Rejected by provider",
    "UNABLE_TO_COMPLETE": "Provider unable to complete",
    "REASSIGNED": "Reassigned",
}

ACTION_LABELS = {
    "ACCEPTED": "Accept job",
    "REJECTED": "Reject job",
    "ON_THE_WAY": "On the way",
    "ARRIVED": "Arrived",
    "IN_PROGRESS": "Start service",
    "COMPLETED": "Complete",
    "UNABLE_TO_COMPLETE": "Unable to complete",
}

_PROVIDER_EVENT = {
    "ACCEPTED": ("PROVIDER_ACCEPTED", "Provider accepted your request"),
    "ON_THE_WAY": ("PROVIDER_ON_THE_WAY", "Provider is on the way"),
    "ARRIVED": ("PROVIDER_ARRIVED", "Provider has arrived"),
    "IN_PROGRESS": ("SERVICE_STARTED", "Service has started"),
    "COMPLETED": ("SERVICE_COMPLETED", "Service completed"),
    "REJECTED": ("PROVIDER_REJECTED", "Provider declined, finding another"),
    "UNABLE_TO_COMPLETE": ("PROVIDER_UNABLE", "Provider unable to complete, finding another"),
}

PRIORITY_ORDER_SQL = ("CASE priority WHEN 'EMERGENCY' THEN 0 WHEN 'URGENT' THEN 1 "
                      "WHEN 'NORMAL' THEN 2 ELSE 3 END")


class LifecycleError(Exception):
    """A business-rule violation. ``message`` is safe to show to the user."""

    def __init__(self, message, status_code=409, code="conflict"):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.code = code


def _env_int(name, default):
    try:
        return int(os.environ.get(name, default))
    except (TypeError, ValueError):
        return int(default)


def status_label(status):
    return STATUS_LABELS.get((status or "").upper(), (status or "").replace("_", " ").title())


def provider_next_actions(status):
    """Statuses a provider may move a job to from ``status`` (for UI buttons)."""
    return list(PROVIDER_TRANSITIONS.get((status or "").upper(), ()))


def _placeholders(values):
    return ",".join("?" * len(values))


def _active_match(conn_or_none, request_id):
    query = (f"SELECT * FROM service_matches WHERE request_id = ? AND status IN "
             f"({_placeholders(ACTIVE_MATCH_STATUSES)}) ORDER BY id DESC LIMIT 1")
    params = (request_id, *ACTIVE_MATCH_STATUSES)
    if conn_or_none is None:
        return fetch_one(query, params)
    return conn_or_none.execute(query, params).fetchone()


def _add_tracking(conn, request_id, status, notes, provider_id=None, latitude=None, longitude=None,
                  location_source=None, eta_minutes=None):
    conn.execute(
        """
        INSERT INTO tracking (request_id, provider_id, status, latitude, longitude,
                              estimated_arrival_minutes, notes, location_source, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (request_id, provider_id, status, latitude, longitude, eta_minutes, notes, location_source, utc_now()),
    )


# ==========================================================
# CREATE REQUEST
# ==========================================================

def _compact_ml(ml):
    """The part of the ML second opinion worth keeping with a request."""
    if not ml or not ml.get("available"):
        return None
    lr, rf = ml["logistic_regression"], ml["random_forest"]
    return {"logistic_regression": {"problem": lr["problem"], "label": lr.get("label"), "probability": lr["probability"],
                                    "top_words": lr.get("top_words", [])},
            "random_forest": {"problem": rf["problem"], "label": rf.get("label"), "probability": rf["probability"]},
            "models_agree": ml.get("models_agree"), "agrees_with_rules": ml.get("agrees_with_rules")}


def create_request(user_id, description, vehicle_id=None, latitude=None, longitude=None,
                   problem_override=None, *, analyzer, matcher, diagnosis_engine, health_engine):
    """
    Store a driver's breakdown report, then try to assign a provider.

    Returns a dict with request_id, analysis, matching, diagnosis, health and
    assignment. Raises ValidationError / LifecycleError for invalid input.
    """

    description = clean_text(description, "Problem description", 2000, required=True, min_length=5)
    lat, lon = parse_coordinates(latitude, longitude)

    if vehicle_id not in (None, ""):
        try:
            vehicle_id = int(vehicle_id)
        except (TypeError, ValueError):
            raise ValidationError("Vehicle selection is invalid.") from None
        if not fetch_one("SELECT id FROM vehicles WHERE id = ? AND user_id = ?", (vehicle_id, user_id)):
            raise LifecycleError("The selected vehicle does not belong to your account.", 403, "forbidden")
    else:
        vehicle_id = None

    max_active = _env_int("RSA_MAX_ACTIVE_REQUESTS_PER_DRIVER", 1)
    open_requests = fetch_all(
        f"SELECT id FROM assistance_requests WHERE user_id = ? AND status IN ({_placeholders(OPEN_REQUEST_STATUSES)}) "
        "ORDER BY id DESC",
        (user_id, *OPEN_REQUEST_STATUSES),
    )
    if len(open_requests) >= max_active:
        raise LifecycleError(
            f"You already have an active assistance request (#{open_requests[0]['id']}). "
            "Track or cancel it before creating a new one.",
            409,
            "active_request_exists",
        )

    analysis = analyzer.analyze(description, problem_override=problem_override)
    match = matcher.match_assistance(analysis["problem"], analysis["severity"], analysis["safe_to_drive"])
    diagnosis = diagnosis_engine.diagnose(analysis["problem"], description, analysis)
    health = health_engine.analyze(description, analysis["problem"], analysis["severity"], analysis["safe_to_drive"])

    now = utc_now()

    with transaction() as conn:
        cursor = conn.execute(
            """
            INSERT INTO assistance_requests
                (user_id, vehicle_id, incident_type, description, priority, recommended_service,
                 escalation, safe_to_drive, status, latitude, longitude, created_at, updated_at,
                 ai_incident_type)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'REQUESTED', ?, ?, ?, ?, ?)
            """,
            (
                # Same format as the existing records: the service display name
                # (e.g. "Mechanic / Roadside Assistance"); matching resolves names and ids.
                user_id, vehicle_id, analysis["problem"], description, match["priority"], match["service_name"],
                1 if match["escalation_required"] else 0, 1 if analysis["safe_to_drive"] else 0,
                lat, lon, now, now, analysis.get("ai_problem"),
            ),
        )
        request_id = cursor.lastrowid

        explanation = {
            "summary": diagnosis.get("diagnosis"),
            "is_confirmed": False,
            "evidence": analysis.get("evidence", []),
            "hazards": [h["hazard"] for h in analysis.get("hazards", [])],
            "likely_causes": diagnosis.get("likely_causes", []),
            "safety_steps": diagnosis.get("safety_steps", []),
            "recommend_towing": diagnosis.get("recommend_towing"),
            "driver_corrected": analysis.get("driver_corrected", False),
            "ai_problem": analysis.get("ai_problem"),
            "confidence_basis": analysis.get("confidence_basis"),
            "decision_source": analysis.get("decision_source"),
            "ml": _compact_ml(analysis.get("ml")),
        }
        conn.execute(
            """
            INSERT INTO diagnosis_records (request_id, diagnosis, severity, confidence, explanation, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (request_id, diagnosis.get("title") or analysis["problem"], analysis["severity"],
             analysis.get("confidence"), json.dumps(explanation), now),
        )

        _add_tracking(
            conn, request_id, "REQUESTED",
            "Request received" + (" with driver location." if lat is not None else " without a shared location."),
            latitude=lat, longitude=lon, location_source="driver" if lat is not None else None,
        )

        if vehicle_id is not None:
            affected = {
                "engine_overheating": "engine", "engine_failure": "engine", "brake_failure": "brake",
                "tyre_puncture": "tyre", "battery_failure": "battery", "electrical_failure": "electrical",
                "fuel_problem": None, "accident": None,
            }.get(analysis["problem"])
            statuses = {part: "NOT ASSESSED" for part in ("engine", "brake", "tyre", "battery", "electrical")}
            if affected:
                statuses[affected] = f"ISSUE REPORTED ({analysis['severity']})"
            conn.execute(
                """
                INSERT INTO vehicle_health (vehicle_id, health_score, engine_status, brake_status, tyre_status,
                                            battery_status, electrical_status, overall_status, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (vehicle_id, health.get("health_score"), statuses["engine"], statuses["brake"], statuses["tyre"],
                 statuses["battery"], statuses["electrical"],
                 f"{health.get('health_status', 'UNKNOWN')} (incident-based, no sensor data)", now),
            )

    notifications.notify(
        user_id, "REQUEST_CREATED", f"Request #{request_id} received",
        f"We received your report ({analysis.get('problem_label', analysis['problem'])}, "
        f"{analysis['severity']} severity). Matching a suitable provider now.",
        request_id, f"created:{request_id}",
    )

    try:
        assignment = assign_best_provider(request_id)
    except Exception:  # noqa: BLE001 - the stored request must survive assignment failures
        logger.exception("Assignment failed for request %s; it stays REQUESTED for retry", request_id)
        assignment = {"assigned": False, "reason": "assignment_error",
                      "message": "Your request is saved. Provider matching will be retried."}

    return {
        "request_id": request_id,
        "analysis": analysis,
        "matching": match,
        "diagnosis": diagnosis,
        "health": health,
        "assignment": assignment,
    }


# ==========================================================
# ASSIGNMENT
# ==========================================================

def _previously_failed_providers(request_id):
    rows = fetch_all(
        "SELECT DISTINCT provider_id FROM service_matches WHERE request_id = ? "
        "AND status IN ('REJECTED', 'UNABLE_TO_COMPLETE', 'REASSIGNED')",
        (request_id,),
    )
    return {row["provider_id"] for row in rows}


def _summarize_exclusions(excluded):
    reasons = {}
    for item in excluded:
        key = item["reason"].split(" (")[0]
        reasons[key] = reasons.get(key, 0) + 1
    return reasons


def assign_best_provider(request_id, exclude_provider_ids=(), preferred_provider_id=None):
    """
    Assign the best eligible provider to a REQUESTED request.

    Idempotent: a request that already has an active match is returned as-is.
    Returns {"assigned": bool, ...}. Never assigns an unsuitable provider; when no
    provider is eligible the request stays REQUESTED and the driver (and admins,
    for emergencies) are notified.
    """

    request = fetch_one("SELECT * FROM assistance_requests WHERE id = ?", (request_id,))
    if not request:
        raise LifecycleError("Request not found.", 404, "not_found")

    if request["status"] != "REQUESTED":
        active = _active_match(None, request_id)
        return {
            "assigned": bool(active),
            "already_assigned": bool(active),
            "match_id": active["id"] if active else None,
            "provider_id": active["provider_id"] if active else None,
            "reason": None if active else f"request is {request['status']}",
        }

    exclude = set(exclude_provider_ids or ()) | _previously_failed_providers(request_id)
    ranking = rank_providers(
        request["recommended_service"], request["latitude"], request["longitude"],
        priority=request["priority"], exclude_provider_ids=exclude,
    )
    candidates = ranking["candidates"]

    if preferred_provider_id is not None:
        candidates = [c for c in candidates if c["provider"]["id"] == int(preferred_provider_id)]

    capacity = _env_int("RSA_PROVIDER_MAX_ACTIVE_JOBS", 1)

    for candidate in candidates:
        provider = candidate["provider"]
        assigned_match_id = None

        with transaction() as conn:
            current = conn.execute("SELECT status FROM assistance_requests WHERE id = ?", (request_id,)).fetchone()
            if not current or current["status"] != "REQUESTED":
                break  # someone else changed it; report below
            if _active_match(conn, request_id):
                break

            busy = conn.execute(
                f"SELECT COUNT(*) FROM service_matches WHERE provider_id = ? AND status IN "
                f"({_placeholders(ACTIVE_MATCH_STATUSES)})",
                (provider["id"], *ACTIVE_MATCH_STATUSES),
            ).fetchone()[0]
            if busy >= capacity:
                continue  # provider took another job meanwhile; try the next one

            now = utc_now()
            cursor = conn.execute(
                """
                INSERT INTO service_matches (request_id, provider_id, match_score, distance_km, status,
                                             created_at, updated_at, match_details)
                VALUES (?, ?, ?, ?, 'ASSIGNED', ?, ?, ?)
                """,
                (request_id, provider["id"], candidate["score"], candidate["distance_km"], now, now,
                 json.dumps(candidate["breakdown"])),
            )
            assigned_match_id = cursor.lastrowid
            updated = conn.execute(
                "UPDATE assistance_requests SET status = 'ASSIGNED', updated_at = ? WHERE id = ? AND status = 'REQUESTED'",
                (now, request_id),
            ).rowcount
            if updated != 1:
                raise LifecycleError("Request changed during assignment; please retry.", 409)

            distance_text = (f"{candidate['distance_km']} km straight-line"
                             if candidate["distance_km"] is not None else "distance unknown")
            _add_tracking(
                conn, request_id, "ASSIGNED",
                f"Assigned to {provider['business_name']} ({distance_text}), "
                "matched on service suitability, distance and rating.",
                provider_id=provider["id"],
            )

        if assigned_match_id is None:
            continue

        notifications.notify(
            request["user_id"], "PROVIDER_ASSIGNED", f"Provider assigned to request #{request_id}",
            f"{provider['business_name']} has been assigned. You will be notified when they accept and set off.",
            request_id, f"assigned:{assigned_match_id}",
        )
        if provider.get("user_id"):
            notifications.notify(
                provider["user_id"], "JOB_ASSIGNED", f"New job #{assigned_match_id} ({request['priority']})",
                f"A {request['incident_type'].replace('_', ' ')} request has been assigned to you. "
                "Accept or reject it from your dashboard.",
                request_id, f"job:{assigned_match_id}",
            )
        return {
            "assigned": True,
            "match_id": assigned_match_id,
            "provider_id": provider["id"],
            "provider": {k: provider.get(k) for k in ("id", "business_name", "service_type", "phone", "rating")},
            "distance_km": candidate["distance_km"],
            "score": candidate["score"],
            "breakdown": candidate["breakdown"],
        }

    # ---- No provider assigned -------------------------------------------
    request = fetch_one("SELECT * FROM assistance_requests WHERE id = ?", (request_id,))
    if request["status"] != "REQUESTED":
        active = _active_match(None, request_id)
        return {"assigned": bool(active), "already_assigned": bool(active),
                "match_id": active["id"] if active else None,
                "provider_id": active["provider_id"] if active else None}

    reasons = _summarize_exclusions(ranking["excluded"])
    attempt = fetch_one("SELECT COUNT(*) AS c FROM service_matches WHERE request_id = ?", (request_id,))["c"]
    note = "No eligible provider is available right now. The request stays open and will be matched automatically."

    last = fetch_one("SELECT status, notes FROM tracking WHERE request_id = ? ORDER BY id DESC LIMIT 1", (request_id,))
    if not last or last["notes"] != note:
        with transaction() as conn:
            _add_tracking(conn, request_id, "REQUESTED", note)

    notifications.notify(
        request["user_id"], "NO_PROVIDER_AVAILABLE", f"Still looking for a provider (request #{request_id})",
        "No suitable provider is available at the moment. Your request is saved and will be assigned as soon "
        "as one becomes available." + (" If anyone is in danger, call 112 now." if request["priority"] == "EMERGENCY" else ""),
        request_id, f"noprov:{request_id}:{attempt}",
    )
    if request["priority"] in ("EMERGENCY", "URGENT"):
        notifications.notify_admins(
            "NO_PROVIDER_AVAILABLE", f"{request['priority']} request #{request_id} has no provider",
            f"No eligible provider for {request['recommended_service']}. Exclusions: {reasons or 'no providers available'}.",
            request_id, f"admin-noprov:{request_id}:{attempt}",
        )

    return {
        "assigned": False,
        "reason": "no_eligible_provider",
        "message": note,
        "excluded_summary": reasons,
        "preferred_provider_rejected": preferred_provider_id is not None,
    }


# ==========================================================
# PROVIDER JOB TRANSITIONS
# ==========================================================

def transition_match(match_id, new_status, *, provider_user_id=None, provider_id=None, note=None):
    """
    Move a provider job (service match) to ``new_status``.

    Ownership: pass ``provider_user_id`` (web) or ``provider_id`` (CLI). A job
    that belongs to someone else is reported as "not found" so its existence is
    not revealed.
    """

    status = str(new_status or "").strip().upper().replace(" ", "_").replace("-", "_")
    if status not in PROVIDER_STATUSES:
        raise LifecycleError("Invalid job status.", 400, "invalid_status")

    note = clean_text(note, "Note", 500) or None
    if status == "UNABLE_TO_COMPLETE" and not note:
        raise LifecycleError("Please give a reason why the job cannot be completed.", 400, "reason_required")

    with transaction() as conn:
        match = conn.execute(
            """
            SELECT sm.*, p.user_id AS provider_user_id, p.business_name,
                   ar.status AS request_status, ar.user_id AS driver_id, ar.priority, ar.id AS req_id
            FROM service_matches sm
            JOIN providers p ON p.id = sm.provider_id
            JOIN assistance_requests ar ON ar.id = sm.request_id
            WHERE sm.id = ?
            """,
            (match_id,),
        ).fetchone()

        if (
            not match
            or (provider_user_id is not None and match["provider_user_id"] != provider_user_id)
            or (provider_id is not None and match["provider_id"] != int(provider_id))
        ):
            raise LifecycleError("Job not found.", 404, "not_found")

        current = (match["status"] or "ASSIGNED").upper()

        if status == current:
            return {"status": current, "request_id": match["request_id"], "unchanged": True,
                    "message": "Status is unchanged."}

        if current in TERMINAL_MATCH_STATUSES:
            raise LifecycleError(f"This job is {status_label(current).lower()} and can no longer be updated.")

        if match["request_status"] in ("CANCELLED", "COMPLETED"):
            raise LifecycleError(f"The request is already {match['request_status'].lower()}.")

        allowed = PROVIDER_TRANSITIONS.get(current, ())
        if status not in allowed:
            nice = ", ".join(ACTION_LABELS.get(s, s) for s in allowed) or "none"
            raise LifecycleError(
                f"Cannot change job status from {current} to {status}. Allowed next steps: {nice}."
            )

        now = utc_now()
        changed = conn.execute(
            "UPDATE service_matches SET status = ?, status_reason = COALESCE(?, status_reason), updated_at = ? "
            "WHERE id = ? AND status = ?",
            (status, note, now, match_id, match["status"]),
        ).rowcount
        if changed != 1:
            raise LifecycleError("The job was updated by someone else. Refresh and try again.")

        if status in ("REJECTED", "UNABLE_TO_COMPLETE"):
            conn.execute(
                "UPDATE assistance_requests SET status = 'REQUESTED', updated_at = ? WHERE id = ? "
                "AND status NOT IN ('CANCELLED', 'COMPLETED')",
                (now, match["request_id"]),
            )
            _add_tracking(
                conn, match["request_id"], status,
                f"{match['business_name']}: {status_label(status).lower()}"
                + (f" ({note})" if note else "") + ". Finding another provider.",
                provider_id=match["provider_id"],
            )
        else:
            conn.execute(
                "UPDATE assistance_requests SET status = ?, updated_at = ? WHERE id = ?",
                (status, now, match["request_id"]),
            )
            _add_tracking(
                conn, match["request_id"], status,
                f"{match['business_name']}: {status_label(status).lower()}." + (f" Notes: {note}" if note else ""),
                provider_id=match["provider_id"],
            )

    # ---- after commit ------------------------------------------------------
    event, title = _PROVIDER_EVENT[status]
    notifications.notify(
        match["driver_id"], event, f"{title} (request #{match['request_id']})",
        f"{match['business_name']}: {status_label(status)}." + (f" Note: {note}" if note else ""),
        match["request_id"], f"{event}:{match_id}",
    )

    reassignment = None
    if status in ("REJECTED", "UNABLE_TO_COMPLETE"):
        if match["priority"] == "EMERGENCY":
            notifications.notify_admins(
                "EMERGENCY_ESCALATED", f"Emergency request #{match['request_id']} lost its provider",
                f"{match['business_name']} {status_label(status).lower()}. Automatic reassignment attempted.",
                match["request_id"], f"esc-lost:{match_id}",
            )
        try:
            reassignment = assign_best_provider(match["request_id"], exclude_provider_ids={match["provider_id"]})
        except Exception:  # noqa: BLE001
            logger.exception("Reassignment failed for request %s", match["request_id"])
            reassignment = {"assigned": False, "reason": "assignment_error"}
    elif status == "COMPLETED":
        try:
            retry_unassigned(limit=5)  # this provider is free again
        except Exception:  # noqa: BLE001
            logger.exception("Retry of unassigned requests failed")

    return {"status": status, "request_id": match["request_id"], "unchanged": False,
            "reassignment": reassignment}


def transition_request_active_match(request_id, new_status, provider_id=None, note=None):
    """CLI helper: transition whatever match is active for ``request_id``."""
    match = _active_match(None, request_id)
    if not match:
        raise LifecycleError("This request has no active provider job.", 409)
    return transition_match(match["id"], new_status, provider_id=provider_id, note=note)


# ==========================================================
# CANCELLATION
# ==========================================================

def cancel_request(request_id, actor_user_id, actor_role, reason=None):
    reason = clean_text(reason, "Reason", 300) or None

    with transaction() as conn:
        request = conn.execute("SELECT * FROM assistance_requests WHERE id = ?", (request_id,)).fetchone()
        if not request or (actor_role == "driver" and request["user_id"] != actor_user_id):
            raise LifecycleError("Request not found.", 404, "not_found")
        if actor_role not in ("driver", "admin"):
            raise LifecycleError("Only the driver or an administrator can cancel a request.", 403, "forbidden")

        if request["status"] == "CANCELLED":
            return {"status": "CANCELLED", "unchanged": True}
        if request["status"] == "COMPLETED":
            raise LifecycleError("A completed request cannot be cancelled.")
        if actor_role == "driver" and request["status"] not in DRIVER_CANCELLABLE:
            raise LifecycleError(
                "Service work has already started, so the request can no longer be cancelled here. "
                "Please speak to the provider."
            )

        now = utc_now()
        changed = conn.execute(
            "UPDATE assistance_requests SET status = 'CANCELLED', updated_at = ? WHERE id = ? AND status = ?",
            (now, request_id, request["status"]),
        ).rowcount
        if changed != 1:
            raise LifecycleError("The request was updated meanwhile. Refresh and try again.")

        match = _active_match(conn, request_id)
        provider_user = None
        if match:
            conn.execute(
                "UPDATE service_matches SET status = 'CANCELLED', status_reason = ?, updated_at = ? WHERE id = ?",
                (f"Cancelled by {actor_role}" + (f": {reason}" if reason else ""), now, match["id"]),
            )
            provider_user = conn.execute("SELECT user_id FROM providers WHERE id = ?",
                                         (match["provider_id"],)).fetchone()

        who = "Driver" if actor_role == "driver" else "Administrator"
        _add_tracking(conn, request_id, "CANCELLED",
                      f"{who} cancelled the request." + (f" Reason: {reason}" if reason else ""),
                      provider_id=match["provider_id"] if match else None)

    if match and provider_user and provider_user["user_id"]:
        notifications.notify(
            provider_user["user_id"], "JOB_CANCELLED", f"Job #{match['id']} cancelled",
            f"Request #{request_id} was cancelled by the {actor_role}. You do not need to continue.",
            request_id, f"jobcancel:{match['id']}",
        )
    notifications.notify(
        request["user_id"], "REQUEST_CANCELLED", f"Request #{request_id} cancelled",
        "Your assistance request has been cancelled" + (" by an administrator." if actor_role == "admin" else "."),
        request_id, f"cancel:{request_id}",
    )
    if match:
        try:
            retry_unassigned(limit=5)
        except Exception:  # noqa: BLE001
            logger.exception("Retry of unassigned requests failed")
    return {"status": "CANCELLED", "unchanged": False}


# ==========================================================
# ADMIN REASSIGNMENT
# ==========================================================

def admin_reassign(request_id, admin_user_id, provider_id=None, reason=None):
    """Controlled reassignment: release the current provider and match again.

    When ``provider_id`` is given it must be eligible (available, approved,
    compatible, within radius, free); this is validated before anything changes.
    """

    reason = clean_text(reason, "Reason", 300, required=True, min_length=3)
    request = fetch_one("SELECT * FROM assistance_requests WHERE id = ?", (request_id,))
    if not request:
        raise LifecycleError("Request not found.", 404, "not_found")
    if request["status"] not in REASSIGNABLE:
        raise LifecycleError(f"A request that is {request['status'].lower()} cannot be reassigned.")

    current = _active_match(None, request_id)
    exclude = {current["provider_id"]} if current else set()

    if provider_id is not None:
        provider_id = int(provider_id)
        if current and provider_id == current["provider_id"]:
            raise LifecycleError("That provider is already assigned to this request.")
        ranking = rank_providers(request["recommended_service"], request["latitude"], request["longitude"],
                                 priority=request["priority"],
                                 exclude_provider_ids=exclude | _previously_failed_providers(request_id))
        if not any(c["provider"]["id"] == provider_id for c in ranking["candidates"]):
            why = next((e["reason"] for e in ranking["excluded"] if e["provider_id"] == provider_id),
                       "provider is not available")
            raise LifecycleError(f"That provider cannot take this request: {why}.")

    old_provider_user = None
    with transaction() as conn:
        now = utc_now()
        if current:
            changed = conn.execute(
                "UPDATE service_matches SET status = 'REASSIGNED', status_reason = ?, updated_at = ? "
                "WHERE id = ? AND status = ?",
                (f"Reassigned by administrator: {reason}", now, current["id"], current["status"]),
            ).rowcount
            if changed != 1:
                raise LifecycleError("The job changed meanwhile. Refresh and try again.")
            old_provider_user = conn.execute("SELECT user_id FROM providers WHERE id = ?",
                                             (current["provider_id"],)).fetchone()
        conn.execute("UPDATE assistance_requests SET status = 'REQUESTED', updated_at = ? WHERE id = ?",
                     (now, request_id))
        _add_tracking(conn, request_id, "REQUESTED", f"Reassignment by administrator: {reason}",
                      provider_id=current["provider_id"] if current else None)

    if current and old_provider_user and old_provider_user["user_id"]:
        notifications.notify(
            old_provider_user["user_id"], "JOB_CANCELLED", f"Job #{current['id']} reassigned",
            "An administrator reassigned this request to another provider. You do not need to continue.",
            request_id, f"jobreassign:{current['id']}",
        )
    notifications.notify(
        request["user_id"], "REQUEST_REASSIGNED", f"Request #{request_id} is being reassigned",
        "An administrator is assigning a different provider to your request.",
        request_id, f"reassign:{request_id}:{current['id'] if current else 0}",
    )

    result = assign_best_provider(request_id, exclude_provider_ids=exclude, preferred_provider_id=provider_id)
    return {"previous_match_id": current["id"] if current else None, "assignment": result}


# ==========================================================
# PROVIDER LOCATION
# ==========================================================

def update_provider_location(provider_user_id, latitude, longitude, accuracy_m=None, record_tracking=True):
    """
    Record the signed-in provider's current location.

    The provider's profile location is always updated (used for matching).
    A tracking breadcrumb is only stored while the provider has a job in
    ACCEPTED / ON_THE_WAY / ARRIVED, and at most once every 10 seconds, so
    location is not collected when no job needs it.

    ``record_tracking=False`` only updates the base location (e.g. typed in by
    the provider); it is never shown to drivers as a live position.
    """

    provider = fetch_one("SELECT * FROM providers WHERE user_id = ?", (provider_user_id,))
    if not provider:
        raise LifecycleError("Provider profile not found.", 404, "not_found")

    lat, lon = parse_coordinates(latitude, longitude, required=True)
    accuracy = parse_optional_float(accuracy_m, "Accuracy", 0, 100000)
    throttle_seconds = _env_int("RSA_LOCATION_MIN_INTERVAL_SECONDS", 10)

    recorded_for = None
    with transaction() as conn:
        now = utc_now()
        conn.execute("UPDATE providers SET latitude = ?, longitude = ?, location_updated_at = ? WHERE id = ?",
                     (lat, lon, now, provider["id"]))

        job = conn.execute(
            f"SELECT * FROM service_matches WHERE provider_id = ? AND status IN "
            f"({_placeholders(LOCATION_TRACKED_STATUSES)}) ORDER BY id DESC LIMIT 1",
            (provider["id"], *LOCATION_TRACKED_STATUSES),
        ).fetchone()

        if job and record_tracking:
            recent = conn.execute(
                "SELECT 1 FROM tracking WHERE request_id = ? AND provider_id = ? AND location_source = 'provider' "
                "AND updated_at > datetime(?, ?)",
                (job["request_id"], provider["id"], now, f"-{throttle_seconds} seconds"),
            ).fetchone()
            if not recent:
                _add_tracking(
                    conn, job["request_id"], job["status"],
                    "Provider location update" + (f" (±{int(accuracy)} m)" if accuracy is not None else ""),
                    provider_id=provider["id"], latitude=lat, longitude=lon, location_source="provider",
                )
            recorded_for = job["request_id"]

    return {"recorded_for_request": recorded_for, "tracking_active": recorded_for is not None,
            "provider_id": provider["id"]}


# ==========================================================
# TRACKING VIEW (authorization + data assembly)
# ==========================================================

def can_view_request(request_row, user):
    """Driver: own requests. Admin: all. Provider: only requests they hold (or completed) a job for."""
    if not request_row or not user:
        return False
    role = user["role"]
    if role == "admin":
        return True
    if role == "driver":
        return request_row["user_id"] == user["id"]
    if role == "provider":
        row = fetch_one(
            "SELECT 1 FROM service_matches sm JOIN providers p ON p.id = sm.provider_id "
            f"WHERE sm.request_id = ? AND p.user_id = ? AND sm.status IN "
            f"({_placeholders(ACTIVE_MATCH_STATUSES + ('COMPLETED',))})",
            (request_row["id"], user["id"], *ACTIVE_MATCH_STATUSES, "COMPLETED"),
        )
        return bool(row)
    return False


def get_tracking_view(request_id, user):
    request = fetch_one(
        """
        SELECT ar.*, v.registration_number, v.make, v.model, u.name AS driver_name, u.phone AS driver_phone
        FROM assistance_requests ar
        JOIN users u ON u.id = ar.user_id
        LEFT JOIN vehicles v ON v.id = ar.vehicle_id
        WHERE ar.id = ?
        """,
        (request_id,),
    )
    if not request or not can_view_request(request, user):
        raise LifecycleError("Request not found.", 404, "not_found")

    req = dict(request)
    is_open = req["status"] in OPEN_REQUEST_STATUSES

    match = fetch_one(
        """
        SELECT sm.id, sm.provider_id, sm.status, sm.match_score, sm.distance_km, sm.created_at, sm.updated_at,
               sm.match_details, p.business_name, p.service_type, p.phone, p.rating, p.user_id AS provider_user_id
        FROM service_matches sm JOIN providers p ON p.id = sm.provider_id
        WHERE sm.request_id = ?
        ORDER BY CASE WHEN sm.status IN ('ASSIGNED','ACCEPTED','ON_THE_WAY','ARRIVED','IN_PROGRESS') THEN 0
                      WHEN sm.status = 'COMPLETED' THEN 1 ELSE 2 END, sm.id DESC
        LIMIT 1
        """,
        (request_id,),
    )
    match = dict(match) if match else None
    if match and match["status"] not in ACTIVE_MATCH_STATUSES + ("COMPLETED",):
        match = None  # a rejected/reassigned/cancelled provider is not "your provider"
    if match:
        try:
            match["match_details"] = json.loads(match["match_details"] or "null")
        except (TypeError, ValueError):
            match["match_details"] = None
        match["status_label"] = status_label(match["status"])
        match.pop("provider_user_id", None)

    history = [dict(r) for r in fetch_all(
        "SELECT id, status, notes, updated_at, provider_id, location_source FROM tracking "
        "WHERE request_id = ? ORDER BY id ASC",
        (request_id,),
    )]
    timeline = [h for h in history if not (h["location_source"] == "provider" and
                                           (h["notes"] or "").startswith("Provider location update"))]
    for item in timeline:
        item["status_label"] = status_label(item["status"])

    provider_location = None
    if match and is_open and match["status"] in LOCATION_TRACKED_STATUSES + ("IN_PROGRESS",):
        loc = fetch_one(
            "SELECT latitude, longitude, updated_at, notes, "
            "CAST((julianday('now') - julianday(updated_at)) * 86400 AS INTEGER) AS age_seconds "
            "FROM tracking WHERE request_id = ? AND provider_id = ? AND location_source = 'provider' "
            "AND latitude IS NOT NULL ORDER BY id DESC LIMIT 1",
            (request_id, match["provider_id"]),
        )
        if loc:
            stale_after = _env_int("RSA_LOCATION_STALE_SECONDS", 120)
            provider_location = {
                "latitude": loc["latitude"], "longitude": loc["longitude"], "updated_at": loc["updated_at"],
                "age_seconds": loc["age_seconds"], "stale": (loc["age_seconds"] or 0) > stale_after,
                "note": loc["notes"],
            }

    driver_location = None
    if req["latitude"] is not None and req["longitude"] is not None:
        driver_location = {"latitude": req["latitude"], "longitude": req["longitude"]}

    # Until live sharing starts, show the assigned provider's registered base
    # location, clearly marked as NOT live (never presented as movement).
    provider_base_location = None
    base_distance = None
    if match and is_open and not provider_location and match["status"] in ACTIVE_MATCH_STATUSES:
        base = fetch_one("SELECT latitude, longitude, location_updated_at FROM providers WHERE id = ?",
                         (match["provider_id"],))
        if base and haversine(base["latitude"], base["longitude"], base["latitude"], base["longitude"]) is not None:
            provider_base_location = {
                "latitude": base["latitude"], "longitude": base["longitude"],
                "updated_at": base["location_updated_at"], "is_live": False,
            }
            if driver_location:
                base_distance = haversine(driver_location["latitude"], driver_location["longitude"],
                                          base["latitude"], base["longitude"])

    live_distance = None
    if provider_location and driver_location:
        live_distance = haversine(driver_location["latitude"], driver_location["longitude"],
                                  provider_location["latitude"], provider_location["longitude"])

    diagnosis = fetch_one(
        "SELECT diagnosis, severity, confidence, explanation, created_at FROM diagnosis_records "
        "WHERE request_id = ? ORDER BY id DESC LIMIT 1",
        (request_id,),
    )
    diagnosis = dict(diagnosis) if diagnosis else None
    if diagnosis:
        try:
            parsed = json.loads(diagnosis["explanation"])
            diagnosis["details"] = parsed if isinstance(parsed, dict) else None
        except (TypeError, ValueError):
            diagnosis["details"] = None  # legacy plain-text explanation
        if diagnosis["details"]:
            diagnosis["explanation"] = diagnosis["details"].get("summary") or ""

    feedback = fetch_one("SELECT rating, comment, created_at FROM service_feedback WHERE request_id = ?",
                         (request_id,))

    role = user["role"]
    actions = {
        "can_cancel": (role == "driver" and req["status"] in DRIVER_CANCELLABLE)
                      or (role == "admin" and is_open),
        "can_give_feedback": role == "driver" and req["status"] == "COMPLETED" and not feedback and match is not None,
        "provider_next": provider_next_actions(match["status"]) if (role == "provider" and match and is_open) else [],
    }

    # Minimise exposure: providers see the driver's contact only while they hold the job.
    if role == "provider" and (not match or match["status"] == "COMPLETED"):
        req["driver_phone"] = None
    if role == "driver":
        req.pop("driver_phone", None)

    req["status_label"] = status_label(req["status"])
    from ai.incident_analyzer import PROBLEM_LABELS
    incident = req["incident_type"] or "unknown"
    req["incident_label"] = PROBLEM_LABELS.get(incident, incident.replace("_", " ").title())

    return {
        "request": req,
        "provider": match,
        "timeline": timeline,
        "provider_location": provider_location,
        "driver_location": driver_location,
        "live_distance_km": live_distance,
        "provider_base_location": provider_base_location,
        "base_distance_km": base_distance,
        "diagnosis": diagnosis,
        "feedback": dict(feedback) if feedback else None,
        "actions": actions,
        "is_open": is_open,
    }


# ==========================================================
# FEEDBACK
# ==========================================================

def submit_feedback(request_id, user_id, rating, comment=None):
    try:
        rating = int(rating)
    except (TypeError, ValueError):
        raise ValidationError("Rating must be a whole number from 1 to 5.") from None
    if not 1 <= rating <= 5:
        raise ValidationError("Rating must be from 1 to 5.")
    comment = clean_text(comment, "Comment", 1000) or None

    request = fetch_one("SELECT * FROM assistance_requests WHERE id = ? AND user_id = ?", (request_id, user_id))
    if not request:
        raise LifecycleError("Request not found.", 404, "not_found")
    if request["status"] != "COMPLETED":
        raise LifecycleError("Feedback can be given once the service is completed.")
    match = fetch_one("SELECT provider_id FROM service_matches WHERE request_id = ? AND status = 'COMPLETED' "
                      "ORDER BY id DESC LIMIT 1", (request_id,))

    with transaction() as conn:
        if conn.execute("SELECT 1 FROM service_feedback WHERE request_id = ?", (request_id,)).fetchone():
            raise LifecycleError("Feedback for this request was already submitted.")
        conn.execute(
            "INSERT INTO service_feedback (request_id, user_id, provider_id, rating, comment, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (request_id, user_id, match["provider_id"] if match else None, rating, comment, utc_now()),
        )
        if match:
            # Provider rating = average of real driver feedback once feedback exists.
            conn.execute(
                "UPDATE providers SET rating = (SELECT ROUND(AVG(rating), 2) FROM service_feedback "
                "WHERE provider_id = ?) WHERE id = ?",
                (match["provider_id"], match["provider_id"]),
            )
    return {"success": True}


# ==========================================================
# BACKGROUND-STYLE MAINTENANCE (call from admin pages or cron)
# ==========================================================

def retry_unassigned(limit=25):
    """Try to assign open REQUESTED requests, emergencies first."""
    rows = fetch_all(
        f"SELECT id FROM assistance_requests WHERE status = 'REQUESTED' ORDER BY {PRIORITY_ORDER_SQL}, created_at "
        "LIMIT ?",
        (max(1, int(limit)),),
    )
    assigned = 0
    for row in rows:
        try:
            if assign_best_provider(row["id"]).get("assigned"):
                assigned += 1
        except Exception:  # noqa: BLE001
            logger.exception("Retry assignment failed for request %s", row["id"])
    return {"checked": len(rows), "assigned": assigned}


def check_escalations():
    """
    Escalation policy (configurable):
    - EMERGENCY requests unassigned for RSA_ESCALATION_MINUTES (default 5)
      notify all administrators.
    - EMERGENCY jobs not accepted within RSA_ACCEPT_TIMEOUT_MINUTES (default 10)
      notify administrators; with RSA_AUTO_REASSIGN_ON_TIMEOUT=1 the job is
      also released and re-matched.
    No response time is promised to drivers.
    """
    unassigned_minutes = _env_int("RSA_ESCALATION_MINUTES", 5)
    accept_minutes = _env_int("RSA_ACCEPT_TIMEOUT_MINUTES", 10)
    auto_reassign = os.environ.get("RSA_AUTO_REASSIGN_ON_TIMEOUT", "0").strip() in {"1", "true", "yes"}

    escalated = 0
    for row in fetch_all(
        "SELECT id, recommended_service FROM assistance_requests WHERE status = 'REQUESTED' "
        "AND priority = 'EMERGENCY' AND created_at <= datetime('now', ?)",
        (f"-{unassigned_minutes} minutes",),
    ):
        if notifications.notify_admins(
            "EMERGENCY_ESCALATED", f"Emergency request #{row['id']} still unassigned",
            f"No provider has been assigned after {unassigned_minutes} minutes "
            f"(service: {row['recommended_service']}). Manual dispatch may be required.",
            row["id"], f"esc-unassigned:{row['id']}",
        ):
            escalated += 1

    timed_out = 0
    for row in fetch_all(
        "SELECT sm.id, sm.request_id, sm.provider_id FROM service_matches sm "
        "JOIN assistance_requests ar ON ar.id = sm.request_id "
        "WHERE sm.status = 'ASSIGNED' AND ar.priority = 'EMERGENCY' "
        "AND COALESCE(sm.updated_at, sm.created_at) <= datetime('now', ?)",
        (f"-{accept_minutes} minutes",),
    ):
        notifications.notify_admins(
            "EMERGENCY_ESCALATED", f"Emergency job #{row['id']} not accepted",
            f"The assigned provider has not accepted request #{row['request_id']} within {accept_minutes} minutes.",
            row["request_id"], f"esc-unaccepted:{row['id']}",
        )
        timed_out += 1
        if auto_reassign:
            try:
                admin_reassign(row["request_id"], None, None, f"Not accepted within {accept_minutes} minutes")
            except LifecycleError:
                logger.info("Auto-reassign skipped for request %s", row["request_id"])

    return {"escalated_unassigned": escalated, "unaccepted_jobs": timed_out}


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO)
    command = sys.argv[1] if len(sys.argv) > 1 else "maintenance"
    if command in ("maintenance", "escalate", "retry"):
        print("retry:", retry_unassigned())
        print("escalations:", check_escalations())
    else:
        print("Usage: python -m assistance.lifecycle [maintenance]")
