"""Provider data access and matching helpers for the RSA application.

This module intentionally uses the project's existing SQLite layer and schema.
It does not create a second database or change the established provider workflow.
"""

from math import radians, sin, cos, sqrt, atan2
from typing import Optional

from database.database import execute_query, fetch_all, fetch_one


VALID_AVAILABILITY = {"available", "busy", "offline"}


def normalize_service(value):
    """Normalize common labels into service categories used for matching."""
    value = (value or "").strip().lower().replace("-", "_").replace(" ", "_").replace("/", "_")
    aliases = {
        "battery": "battery", "battery_assistance": "battery", "battery_service": "battery", "jump_start": "battery",
        "tyre": "tyre", "tire": "tyre", "tyre_service": "tyre", "tire_service": "tyre", "puncture": "tyre",
        "mechanic": "mechanic", "mechanical": "mechanic", "mechanical_repair": "mechanic", "engine_repair": "mechanic",
        "garage": "mechanic", "workshop": "mechanic",
        "electrical": "electrical", "electrician": "electrical", "auto_electric": "electrical",
        "towing": "recovery", "tow": "recovery", "emergency_recovery": "recovery", "recovery": "recovery",
        "crane": "recovery", "flatbed": "recovery",
        "fuel": "fuel", "fuel_delivery": "fuel", "petrol": "fuel", "diesel": "fuel",
        "general_roadside_assistance": "general", "roadside_assistance": "general", "general": "general",
        "roadside": "general",
    }
    for key, category in aliases.items():
        if key in value:
            return category
    return value


def haversine(lat1, lon1, lat2, lon2):
    """Return great-circle distance in kilometres, or None for missing/invalid coordinates."""
    try:
        if any(value is None or value == "" for value in (lat1, lon1, lat2, lon2)):
            return None
        lat1, lon1, lat2, lon2 = map(float, (lat1, lon1, lat2, lon2))
        if not (-90 <= lat1 <= 90 and -90 <= lat2 <= 90 and -180 <= lon1 <= 180 and -180 <= lon2 <= 180):
            return None
        radius = 6371.0
        p1, p2 = radians(lat1), radians(lat2)
        dp, dl = radians(lat2 - lat1), radians(lon2 - lon1)
        a = sin(dp / 2) ** 2 + cos(p1) * cos(p2) * sin(dl / 2) ** 2
        return round(radius * 2 * atan2(sqrt(a), sqrt(max(0.0, 1.0 - a))), 2)
    except (TypeError, ValueError, OverflowError):
        return None


def get_provider_by_id(provider_id):
    if not provider_id:
        return None
    return fetch_one("SELECT * FROM providers WHERE id = ?", (provider_id,))


def get_provider_by_user_id(user_id):
    if not user_id:
        return None
    return fetch_one("SELECT * FROM providers WHERE user_id = ?", (user_id,))


def get_all_providers(limit=100):
    """Return providers newest first; limit is bounded to avoid unbounded reads."""
    try:
        limit = max(1, min(int(limit), 1000))
    except (TypeError, ValueError):
        limit = 100
    return fetch_all("SELECT * FROM providers ORDER BY id DESC LIMIT ?", (limit,))


ACTIVE_JOB_STATUSES = ("ASSIGNED", "ACCEPTED", "ON_THE_WAY", "ARRIVED", "IN_PROGRESS")


def get_available_providers(service_type=None):
    """Return available providers, optionally filtered by normalized service type.

    Each row also carries runtime state used by matching:
    ``active_jobs`` (open assignments) and ``user_is_active`` (linked account status).
    """
    placeholders = ",".join("?" * len(ACTIVE_JOB_STATUSES))
    rows = fetch_all(
        f"""
        SELECT p.*,
               u.is_active AS user_is_active,
               (SELECT COUNT(*) FROM service_matches sm
                 WHERE sm.provider_id = p.id AND sm.status IN ({placeholders})) AS active_jobs
        FROM providers p
        LEFT JOIN users u ON u.id = p.user_id
        WHERE lower(p.availability) IN ('available', 'busy')
        ORDER BY p.id DESC
        """,
        ACTIVE_JOB_STATUSES,
    )
    if not service_type:
        return rows
    requested = resolve_requested_service(service_type)
    allowed = SERVICE_COMPATIBILITY[requested]
    return [row for row in rows if normalize_service(row["service_type"]) in allowed]


def create_provider(business_name, service_type, phone=None, latitude=None, longitude=None,
                    user_id=None, availability="available", rating=0.0):
    """Create a provider using the existing providers table."""
    name = business_name.strip() if isinstance(business_name, str) else ""
    service = service_type.strip() if isinstance(service_type, str) else ""
    if not name or not service:
        return {"success": False, "message": "Business name and service type are required."}
    availability = (availability or "available").strip().lower()
    if availability not in VALID_AVAILABILITY:
        return {"success": False, "message": "Availability must be available, busy, or offline."}
    try:
        latitude = float(latitude) if latitude not in (None, "") else None
        longitude = float(longitude) if longitude not in (None, "") else None
        rating = float(rating or 0.0)
    except (TypeError, ValueError):
        return {"success": False, "message": "Coordinates and rating must be numeric."}
    if (latitude is None) != (longitude is None):
        return {"success": False, "message": "Provide both latitude and longitude, or neither."}
    if latitude is not None and haversine(latitude, longitude, latitude, longitude) is None:
        return {"success": False, "message": "Coordinates are outside valid ranges."}
    if not 0 <= rating <= 5:
        return {"success": False, "message": "Rating must be between 0 and 5."}
    try:
        provider_id = execute_query(
            """INSERT INTO providers (user_id, business_name, service_type, phone, latitude, longitude, availability, rating)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (user_id, name, service, phone.strip() if isinstance(phone, str) else phone,
             latitude, longitude, availability, rating),
        )
        return {"success": True, "message": "Provider created successfully.", "provider_id": provider_id,
                "provider": dict(get_provider_by_id(provider_id))}
    except Exception as error:
        return {"success": False, "message": f"Could not create provider: {error}"}


def update_provider(provider_id, **fields):
    """Update supported provider fields without permitting arbitrary SQL columns."""
    allowed = {"business_name", "service_type", "phone", "latitude", "longitude", "availability", "rating", "user_id"}
    updates = {key: value for key, value in fields.items() if key in allowed}
    if not provider_id:
        return {"success": False, "message": "Provider ID is required."}
    if not updates:
        return {"success": False, "message": "No supported fields were provided."}
    if not get_provider_by_id(provider_id):
        return {"success": False, "message": "Provider not found."}
    if "availability" in updates:
        updates["availability"] = str(updates["availability"]).strip().lower()
        if updates["availability"] not in VALID_AVAILABILITY:
            return {"success": False, "message": "Availability must be available, busy, or offline."}
    if "rating" in updates:
        try:
            updates["rating"] = float(updates["rating"])
        except (TypeError, ValueError):
            return {"success": False, "message": "Rating must be numeric."}
        if not 0 <= updates["rating"] <= 5:
            return {"success": False, "message": "Rating must be between 0 and 5."}
    for key in ("business_name", "service_type"):
        if key in updates:
            if not isinstance(updates[key], str) or not updates[key].strip():
                return {"success": False, "message": f"{key.replace('_', ' ').title()} cannot be empty."}
            updates[key] = updates[key].strip()
    try:
        assignments = ", ".join(f"{key} = ?" for key in updates)
        execute_query(f"UPDATE providers SET {assignments} WHERE id = ?", (*updates.values(), provider_id))
        return {"success": True, "message": "Provider updated successfully.", "provider": dict(get_provider_by_id(provider_id))}
    except Exception as error:
        return {"success": False, "message": f"Could not update provider: {error}"}


def update_availability(provider_id, availability):
    return update_provider(provider_id, availability=availability)


def update_rating(provider_id, rating):
    return update_provider(provider_id, rating=rating)


def delete_provider(provider_id):
    if not provider_id:
        return {"success": False, "message": "Provider ID is required."}
    if not get_provider_by_id(provider_id):
        return {"success": False, "message": "Provider not found."}
    try:
        execute_query("DELETE FROM providers WHERE id = ?", (provider_id,))
        return {"success": True, "message": "Provider deleted successfully."}
    except Exception as error:
        return {"success": False, "message": f"Could not delete provider: {error}"}


# ==========================================================
# MATCHING
# ==========================================================
#
# One explicit compatibility table replaces substring guessing.
# Before this, "Emergency Roadside Assistance" (brake failure) normalized to
# "general" and was treated as compatible with every specialist, while
# "Emergency Services" (accident), "Fuel Delivery" and "Electrical Vehicle
# Assistance" matched nobody and crashed web.py with IndexError.
#
# Keys are the service IDs produced by assistance.matching.AssistanceMatcher.
# Values: provider category -> suitability (1.0 = specialist, lower = capable
# fallback). Categories not listed are never dispatched for that service.

SERVICE_COMPATIBILITY = {
    "emergency_services": {"recovery": 1.0, "general": 0.6},
    "emergency_roadside_assistance": {"recovery": 1.0, "mechanic": 0.9, "general": 0.7},
    "mechanic_or_roadside_assistance": {"mechanic": 1.0, "general": 0.8, "recovery": 0.6},
    "tyre_assistance": {"tyre": 1.0, "general": 0.8, "mechanic": 0.6},
    "battery_assistance": {"battery": 1.0, "general": 0.8, "mechanic": 0.7, "electrical": 0.6},
    "fuel_delivery": {"fuel": 1.0, "general": 0.8},
    "electrical_vehicle_assistance": {"electrical": 1.0, "mechanic": 0.8, "general": 0.7},
    "general_roadside_assistance": {"general": 1.0, "mechanic": 0.9, "recovery": 0.7},
}

CATEGORY_TO_SERVICE = {
    "tyre": "tyre_assistance",
    "battery": "battery_assistance",
    "mechanic": "mechanic_or_roadside_assistance",
    "recovery": "emergency_roadside_assistance",
    "fuel": "fuel_delivery",
    "electrical": "electrical_vehicle_assistance",
    "general": "general_roadside_assistance",
}

SERVICE_NAMES = {
    "emergency services": "emergency_services",
    "emergency roadside assistance": "emergency_roadside_assistance",
    "mechanic / roadside assistance": "mechanic_or_roadside_assistance",
    "tyre assistance": "tyre_assistance",
    "battery assistance": "battery_assistance",
    "fuel delivery": "fuel_delivery",
    "electrical vehicle assistance": "electrical_vehicle_assistance",
    "general roadside assistance": "general_roadside_assistance",
}

PROVIDER_CATEGORIES = ("mechanic", "tyre", "battery", "electrical", "recovery", "fuel", "general")


def resolve_requested_service(value):
    """Map a service id, service display name or free label to a SERVICE_COMPATIBILITY key."""
    raw = (value or "").strip()
    if raw in SERVICE_COMPATIBILITY:
        return raw
    if raw.lower() in SERVICE_NAMES:
        return SERVICE_NAMES[raw.lower()]
    category = normalize_service(raw)
    return CATEGORY_TO_SERVICE.get(category, "general_roadside_assistance")


def _env_float(name, default):
    import os
    try:
        return float(os.environ.get(name, default))
    except (TypeError, ValueError):
        return float(default)


def rank_providers(service_name, lat, lon, priority=None, exclude_provider_ids=(), max_radius_km=None):
    """
    Rank eligible providers for a request.

    Returns ``{"requested_service", "candidates": [...], "excluded": [...]}`` where
    each candidate is ``{"provider", "distance_km", "score", "breakdown"}`` sorted best
    first, and each exclusion is ``{"provider_id", "business_name", "reason"}``.

    Eligibility (hard rules): available, verification approved, linked account
    active, below the active-job capacity, service compatible, not previously
    rejected for this request, and within the service radius when distance is known.

    Score (0-100): suitability (specialist vs fallback), distance, rating. For
    EMERGENCY requests distance carries more weight. Unrated providers get a
    neutral rating component, and this is reported in the breakdown.
    """
    import os

    requested = resolve_requested_service(service_name)
    allowed = SERVICE_COMPATIBILITY[requested]
    radius = float(max_radius_km) if max_radius_km else _env_float("RSA_MAX_SERVICE_RADIUS_KM", 50)
    capacity = int(_env_float("RSA_PROVIDER_MAX_ACTIVE_JOBS", 1))
    allow_unlinked = os.environ.get("RSA_ALLOW_UNLINKED_PROVIDERS", "0").strip().lower() in {"1", "true", "yes"}
    excluded_ids = {int(x) for x in exclude_provider_ids or () if x is not None}

    if (priority or "").upper() == "EMERGENCY":
        weights = {"suitability": 45.0, "distance": 40.0, "rating": 15.0}
    else:
        weights = {"suitability": 50.0, "distance": 30.0, "rating": 20.0}

    request_has_location = haversine(lat, lon, lat, lon) is not None

    candidates, excluded = [], []
    for row in get_available_providers():
        provider = dict(row)
        pid = provider.get("id")
        name = provider.get("business_name")

        def skip(reason):
            excluded.append({"provider_id": pid, "business_name": name, "reason": reason})

        category = normalize_service(provider.get("service_type"))
        if pid in excluded_ids:
            skip("previously rejected or failed this request")
            continue
        if category not in allowed:
            skip(f"service '{provider.get('service_type')}' not suitable for {requested}")
            continue
        if (provider.get("verification_status") or "approved").lower() != "approved":
            skip("provider verification not approved")
            continue
        if "user_id" in provider and provider.get("user_id") is None and not allow_unlinked:
            skip("no linked provider login, so nobody could accept or update the job")
            continue
        if provider.get("user_is_active") is not None and not provider.get("user_is_active"):
            skip("provider account is deactivated")
            continue
        if int(provider.get("active_jobs") or 0) >= capacity:
            skip("provider already has an active job")
            continue

        distance = haversine(lat, lon, provider.get("latitude"), provider.get("longitude"))
        if distance is not None and distance > radius:
            skip(f"outside service radius ({distance} km > {radius:g} km)")
            continue

        suitability = allowed[category]
        try:
            rating = float(provider.get("rating") or 0.0)
        except (TypeError, ValueError):
            rating = 0.0
        rated = 0 < rating <= 5

        suitability_points = weights["suitability"] * suitability
        distance_points = weights["distance"] * (1 - distance / radius) if distance is not None else 0.0
        rating_points = weights["rating"] * (rating / 5.0 if rated else 0.5)
        score = round(suitability_points + distance_points + rating_points, 2)

        candidates.append({
            "provider": provider,
            "distance_km": distance,
            "score": score,
            "breakdown": {
                "requested_service": requested,
                "provider_category": category,
                "suitability": suitability,
                "suitability_points": round(suitability_points, 2),
                "distance_km": distance,
                "distance_points": round(distance_points, 2),
                "distance_note": (
                    "straight-line distance" if distance is not None else
                    ("request has no location" if not request_has_location else "provider location unknown")
                ),
                "rating": rating if rated else None,
                "rating_points": round(rating_points, 2),
                "rating_note": None if rated else "unrated provider scored as neutral",
                "weights": weights,
                "max_radius_km": radius,
            },
        })

    candidates.sort(key=lambda c: (
        -c["score"],
        c["distance_km"] if c["distance_km"] is not None else float("inf"),
        c["provider"].get("id") or 0,
    ))
    return {"requested_service": requested, "candidates": candidates, "excluded": excluded}


def find_provider(service_name, lat, lon, priority=None, exclude_provider_ids=()):
    """Choose the best eligible provider (see ``rank_providers``).

    Incompatible specialists are never selected; callers handle ``None`` by
    presenting a no-match state. Returns (provider_dict, distance_km), or None.
    """
    ranking = rank_providers(service_name, lat, lon, priority=priority, exclude_provider_ids=exclude_provider_ids)
    if not ranking["candidates"]:
        return None
    best = ranking["candidates"][0]
    return best["provider"], best["distance_km"]
