"""
RSA Provider Requests
---------------------
Handles provider-side viewing and management
of roadside assistance requests.

Includes:
- Request lookup
- Provider request listing
- Pending request listing
- Request status management
- Request statistics
"""

from database.database import (
    execute_query,
    fetch_one,
    fetch_all,
)


# ==========================================================
# CONSTANTS
# ==========================================================

VALID_REQUEST_STATUSES = {
    "REQUESTED",
    "MATCHED",
    "ASSIGNED",
    "ACCEPTED",
    "ON_THE_WAY",
    "ARRIVED",
    "IN_PROGRESS",
    "COMPLETED",
    "CANCELLED",
}


# ==========================================================
# REQUEST LOOKUP
# ==========================================================

def get_request_by_id(request_id: int):
    """
    Return a complete assistance request.
    """

    if not request_id:
        return None

    return fetch_one(
        """
        SELECT
            ar.id,
            ar.user_id,
            ar.vehicle_id,
            ar.incident_type,
            ar.description,
            ar.priority,
            ar.recommended_service,
            ar.escalation,
            ar.safe_to_drive,
            ar.status,
            ar.latitude,
            ar.longitude,
            ar.created_at,
            ar.updated_at,

            u.name AS user_name,
            u.email AS user_email,
            u.phone AS user_phone,

            v.registration_number,
            v.make,
            v.model,
            v.year,
            v.fuel_type

        FROM assistance_requests ar

        JOIN users u
            ON ar.user_id = u.id

        LEFT JOIN vehicles v
            ON ar.vehicle_id = v.id

        WHERE ar.id = ?
        """,
        (request_id,),
    )


# ==========================================================
# PROVIDER REQUESTS
# ==========================================================

def get_provider_requests(provider_id: int):
    """
    Return all assistance requests matched
    to a provider.
    """

    if not provider_id:
        return []

    return fetch_all(
        """
        SELECT
            ar.id,
            ar.user_id,
            ar.vehicle_id,
            ar.incident_type,
            ar.description,
            ar.priority,
            ar.recommended_service,
            ar.escalation,
            ar.safe_to_drive,
            ar.status,
            ar.latitude,
            ar.longitude,
            ar.created_at,
            ar.updated_at,

            sm.id AS match_id,
            sm.match_score,
            sm.distance_km,
            sm.status AS match_status,
            sm.created_at AS match_created_at,

            u.name AS user_name,
            u.email AS user_email,
            u.phone AS user_phone,

            v.registration_number,
            v.make,
            v.model,
            v.year,
            v.fuel_type

        FROM assistance_requests ar

        JOIN service_matches sm
            ON ar.id = sm.request_id

        JOIN users u
            ON ar.user_id = u.id

        LEFT JOIN vehicles v
            ON ar.vehicle_id = v.id

        WHERE sm.provider_id = ?

        ORDER BY ar.created_at DESC
        """,
        (provider_id,),
    )


# ==========================================================
# PENDING REQUESTS
# ==========================================================

def get_pending_requests(provider_id: int):
    """
    Return pending requests assigned to a provider.

    Pending requests are MATCHED or ASSIGNED.
    """

    if not provider_id:
        return []

    return fetch_all(
        """
        SELECT
            ar.id,
            ar.user_id,
            ar.vehicle_id,
            ar.incident_type,
            ar.description,
            ar.priority,
            ar.recommended_service,
            ar.escalation,
            ar.safe_to_drive,
            ar.status,
            ar.latitude,
            ar.longitude,
            ar.created_at,
            ar.updated_at,

            sm.id AS match_id,
            sm.match_score,
            sm.distance_km,
            sm.status AS match_status,
            sm.created_at AS match_created_at,

            u.name AS user_name,
            u.email AS user_email,
            u.phone AS user_phone,

            v.registration_number,
            v.make,
            v.model,
            v.year,
            v.fuel_type

        FROM assistance_requests ar

        JOIN service_matches sm
            ON ar.id = sm.request_id

        JOIN users u
            ON ar.user_id = u.id

        LEFT JOIN vehicles v
            ON ar.vehicle_id = v.id

        WHERE sm.provider_id = ?

        AND sm.status IN (
            'MATCHED',
            'ASSIGNED'
        )

        ORDER BY
            CASE ar.priority
                WHEN 'CRITICAL' THEN 1
                WHEN 'HIGH' THEN 2
                WHEN 'MEDIUM' THEN 3
                WHEN 'LOW' THEN 4
                ELSE 5
            END,

            ar.created_at ASC
        """,
        (provider_id,),
    )


# ==========================================================
# STATUS VALIDATION
# ==========================================================

def validate_request_status(status: str) -> str:
    """
    Validate and normalize a request status.
    """

    if not isinstance(status, str):
        raise ValueError(
            "Status must be a string."
        )

    status = status.strip().upper()

    if status not in VALID_REQUEST_STATUSES:
        raise ValueError(
            "Invalid request status. Allowed values: "
            + ", ".join(sorted(VALID_REQUEST_STATUSES))
        )

    return status


# ==========================================================
# REQUEST STATUS
# ==========================================================

def update_request_status(
    request_id: int,
    status: str,
):
    """
    Update the main assistance request status.
    """

    if not request_id:
        return {
            "success": False,
            "message": "Request ID is required.",
        }

    try:

        status = validate_request_status(
            status
        )

    except ValueError as error:

        return {
            "success": False,
            "message": str(error),
        }

    request = get_request_by_id(
        request_id
    )

    if not request:
        return {
            "success": False,
            "message": "Assistance request not found.",
        }

    # Request status must follow the provider job (service match). Updating
    # assistance_requests alone (as before) left the match and tracking
    # history contradicting the request.
    from assistance.lifecycle import (
        LifecycleError,
        cancel_request,
        transition_request_active_match,
    )

    try:
        if status == "CANCELLED":
            cancel_request(request_id, None, "admin", "Cancelled from the provider console")
            new_status = "CANCELLED"
        elif status in ("REQUESTED", "MATCHED", "ASSIGNED"):
            return {
                "success": False,
                "message": "This status is set by the matching engine.",
            }
        else:
            new_status = transition_request_active_match(request_id, status)["status"]
    except LifecycleError as error:
        return {
            "success": False,
            "message": error.message,
        }
    except Exception as error:
        return {
            "success": False,
            "message": (
                f"Request status update failed: {error}"
            ),
        }

    return {
        "success": True,
        "message": (
            "Request status updated successfully."
        ),
        "request_id": request_id,
        "status": new_status,
    }


# ==========================================================
# ACCEPT REQUEST
# ==========================================================

def accept_request(request_id: int):
    """
    Accept an assistance request.
    """

    return update_request_status(
        request_id,
        "ACCEPTED",
    )


# ==========================================================
# ON THE WAY
# ==========================================================

def mark_on_the_way(request_id: int):
    """
    Mark provider as being on the way.
    """

    return update_request_status(
        request_id,
        "ON_THE_WAY",
    )


# ==========================================================
# ARRIVAL
# ==========================================================

def mark_arrived(request_id: int):
    """
    Mark provider as arrived.
    """

    return update_request_status(
        request_id,
        "ARRIVED",
    )


# ==========================================================
# START SERVICE
# ==========================================================

def start_service(request_id: int):
    """
    Start roadside assistance service.
    """

    return update_request_status(
        request_id,
        "IN_PROGRESS",
    )


# ==========================================================
# COMPLETE REQUEST
# ==========================================================

def complete_request(request_id: int):
    """
    Complete an assistance request.
    """

    return update_request_status(
        request_id,
        "COMPLETED",
    )


# ==========================================================
# CANCEL REQUEST
# ==========================================================

def cancel_request(request_id: int):
    """
    Cancel an assistance request.
    """

    return update_request_status(
        request_id,
        "CANCELLED",
    )


# ==========================================================
# REQUEST SUMMARY
# ==========================================================

def get_request_summary(provider_id: int):
    """
    Return request statistics for a provider.
    """

    if not provider_id:
        return {
            "total_requests": 0,
            "completed_requests": 0,
            "cancelled_requests": 0,
            "active_requests": 0,
        }

    row = fetch_one(
        """
        SELECT
            COUNT(*) AS total_requests,

            SUM(
                CASE
                    WHEN sm.status = 'COMPLETED'
                    THEN 1
                    ELSE 0
                END
            ) AS completed_requests,

            SUM(
                CASE
                    WHEN sm.status = 'CANCELLED'
                    THEN 1
                    ELSE 0
                END
            ) AS cancelled_requests,

            SUM(
                CASE
                    WHEN sm.status NOT IN (
                        'COMPLETED',
                        'CANCELLED'
                    )
                    THEN 1
                    ELSE 0
                END
            ) AS active_requests

        FROM service_matches sm

        WHERE sm.provider_id = ?
        """,
        (provider_id,),
    )

    if not row:
        return {
            "total_requests": 0,
            "completed_requests": 0,
            "cancelled_requests": 0,
            "active_requests": 0,
        }

    return {
        "total_requests": (
            row["total_requests"] or 0
        ),

        "completed_requests": (
            row["completed_requests"] or 0
        ),

        "cancelled_requests": (
            row["cancelled_requests"] or 0
        ),

        "active_requests": (
            row["active_requests"] or 0
        ),
    }


# ==========================================================
# TEST
# ==========================================================

def run_tests():

    print("=" * 60)
    print("RSA PROVIDER REQUESTS TEST")
    print("=" * 60)

    # ------------------------------------------------------
    # Function availability
    # ------------------------------------------------------

    functions = [
        get_request_by_id,
        get_provider_requests,
        get_pending_requests,
        validate_request_status,
        update_request_status,
        accept_request,
        mark_on_the_way,
        mark_arrived,
        start_service,
        complete_request,
        cancel_request,
        get_request_summary,
    ]

    print(
        "Module import    : PASS"
    )

    print(
        "Functions loaded  :",
        "PASS"
        if all(callable(fn) for fn in functions)
        else "FAIL",
    )

    # ------------------------------------------------------
    # Valid status
    # ------------------------------------------------------

    try:

        status = validate_request_status(
            " accepted "
        )

        print(
            "Valid status      :",
            "PASS"
            if status == "ACCEPTED"
            else "FAIL",
        )

    except Exception:

        print(
            "Valid status      : FAIL"
        )

    # ------------------------------------------------------
    # Invalid status
    # ------------------------------------------------------

    try:

        validate_request_status(
            "INVALID_STATUS"
        )

        print(
            "Invalid status    : FAIL"
        )

    except ValueError:

        print(
            "Invalid status    : PASS"
        )

    # ------------------------------------------------------
    # Missing request
    # ------------------------------------------------------

    request = get_request_by_id(
        999999999
    )

    print(
        "Missing request   :",
        "PASS"
        if request is None
        else "FAIL",
    )

    # ------------------------------------------------------
    # Provider requests
    # ------------------------------------------------------

    provider_requests = get_provider_requests(
        999999999
    )

    print(
        "Provider requests :",
        "PASS"
        if isinstance(provider_requests, list)
        else "FAIL",
    )

    # ------------------------------------------------------
    # Pending requests
    # ------------------------------------------------------

    pending = get_pending_requests(
        999999999
    )

    print(
        "Pending requests   :",
        "PASS"
        if isinstance(pending, list)
        else "FAIL",
    )

    # ------------------------------------------------------
    # Request summary
    # ------------------------------------------------------

    summary = get_request_summary(
        999999999
    )

    print(
        "Request summary   :",
        "PASS"
        if isinstance(summary, dict)
        and summary["total_requests"] == 0
        else "FAIL",
    )

    # ------------------------------------------------------
    # Missing request status
    # ------------------------------------------------------

    update = update_request_status(
        999999999,
        "ACCEPTED",
    )

    print(
        "Status validation :",
        "PASS"
        if not update["success"]
        else "FAIL",
    )

    # ------------------------------------------------------
    # Final
    # ------------------------------------------------------

    print("=" * 60)
    print("RSA PROVIDER REQUESTS TEST COMPLETE")
    print("=" * 60)


# ==========================================================
# ENTRY POINT
# ==========================================================

if __name__ == "__main__":
    run_tests()