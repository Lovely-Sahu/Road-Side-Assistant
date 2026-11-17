"""
RSA Driver Emergency Module
---------------------------
Handles emergency assistance requests for drivers.

Features:
- Create an emergency request
- Validate emergency information
- Check active emergency requests
- Cancel an emergency request
- Retrieve emergency request details
"""

from database.database import (
    execute_query,
    fetch_one,
    fetch_all,
)


# ==========================================================
# CONSTANTS
# ==========================================================

EMERGENCY_PRIORITY = "CRITICAL"

EMERGENCY_STATUS = "EMERGENCY_REQUESTED"


# ==========================================================
# VALIDATION
# ==========================================================

def validate_emergency_data(
    user_id: int,
    incident_type: str,
    description: str = None,
    latitude: float = None,
    longitude: float = None,
):
    """
    Validate emergency request information.
    """

    if not user_id:
        return {
            "success": False,
            "message": "User ID is required.",
        }

    if (
        not isinstance(incident_type, str)
        or not incident_type.strip()
    ):
        return {
            "success": False,
            "message": "Emergency incident type is required.",
        }

    if latitude is not None:
        try:
            latitude = float(latitude)

            if latitude < -90 or latitude > 90:
                return {
                    "success": False,
                    "message": "Invalid latitude.",
                }

        except (TypeError, ValueError):
            return {
                "success": False,
                "message": "Latitude must be a valid number.",
            }

    if longitude is not None:
        try:
            longitude = float(longitude)

            if longitude < -180 or longitude > 180:
                return {
                    "success": False,
                    "message": "Invalid longitude.",
                }

        except (TypeError, ValueError):
            return {
                "success": False,
                "message": "Longitude must be a valid number.",
            }

    return {
        "success": True,
        "message": "Emergency data is valid.",
    }


# ==========================================================
# CHECK ACTIVE EMERGENCY
# ==========================================================

def get_active_emergency(user_id: int):
    """
    Return the driver's currently active emergency request.
    """

    request = fetch_one(
        """
        SELECT
            id,
            user_id,
            vehicle_id,
            incident_type,
            description,
            priority,
            recommended_service,
            escalation,
            safe_to_drive,
            status,
            latitude,
            longitude,
            created_at,
            updated_at
        FROM assistance_requests
        WHERE user_id = ?
        AND escalation = 1
        AND status NOT IN (
            'COMPLETED',
            'CANCELLED'
        )
        ORDER BY created_at DESC
        LIMIT 1
        """,
        (user_id,),
    )

    if not request:
        return None

    return dict(request)


# ==========================================================
# CREATE EMERGENCY REQUEST
# ==========================================================

def create_emergency_request(
    user_id: int,
    incident_type: str,
    description: str = None,
    vehicle_id: int = None,
    latitude: float = None,
    longitude: float = None,
):
    """
    Create a high-priority emergency assistance request.
    """

    validation = validate_emergency_data(
        user_id=user_id,
        incident_type=incident_type,
        description=description,
        latitude=latitude,
        longitude=longitude,
    )

    if not validation["success"]:
        return validation

    # Prevent duplicate active emergency requests.
    active = get_active_emergency(user_id)

    if active:
        return {
            "success": False,
            "message": "You already have an active emergency request.",
            "request_id": active["id"],
        }

    incident_type = incident_type.strip().upper()

    if isinstance(description, str):
        description = description.strip()

    try:
        request_id = execute_query(
            """
            INSERT INTO assistance_requests (
                user_id,
                vehicle_id,
                incident_type,
                description,
                priority,
                recommended_service,
                escalation,
                safe_to_drive,
                status,
                latitude,
                longitude
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                vehicle_id,
                incident_type,
                description,
                EMERGENCY_PRIORITY,
                "Emergency Roadside Assistance",
                1,
                0,
                EMERGENCY_STATUS,
                latitude,
                longitude,
            ),
        )

        return {
            "success": True,
            "message": "Emergency assistance request created successfully.",
            "request_id": request_id,
            "priority": EMERGENCY_PRIORITY,
            "status": EMERGENCY_STATUS,
        }

    except Exception as error:
        return {
            "success": False,
            "message": f"Emergency request failed: {error}",
        }


# ==========================================================
# GET EMERGENCY REQUEST
# ==========================================================

def get_emergency_request(
    request_id: int,
    user_id: int = None,
):
    """
    Return an emergency request.

    When user_id is supplied, only that driver's request
    can be returned.
    """

    if user_id is None:

        request = fetch_one(
            """
            SELECT
                id,
                user_id,
                vehicle_id,
                incident_type,
                description,
                priority,
                recommended_service,
                escalation,
                safe_to_drive,
                status,
                latitude,
                longitude,
                created_at,
                updated_at
            FROM assistance_requests
            WHERE id = ?
            AND escalation = 1
            """,
            (request_id,),
        )

    else:

        request = fetch_one(
            """
            SELECT
                id,
                user_id,
                vehicle_id,
                incident_type,
                description,
                priority,
                recommended_service,
                escalation,
                safe_to_drive,
                status,
                latitude,
                longitude,
                created_at,
                updated_at
            FROM assistance_requests
            WHERE id = ?
            AND user_id = ?
            AND escalation = 1
            """,
            (
                request_id,
                user_id,
            ),
        )

    if not request:
        return None

    return dict(request)


# ==========================================================
# EMERGENCY HISTORY
# ==========================================================

def get_emergency_history(
    user_id: int,
    limit: int = 10,
):
    """
    Return previous emergency requests for a driver.
    """

    if limit <= 0:
        limit = 10

    requests = fetch_all(
        """
        SELECT
            id,
            vehicle_id,
            incident_type,
            description,
            priority,
            recommended_service,
            escalation,
            safe_to_drive,
            status,
            latitude,
            longitude,
            created_at,
            updated_at
        FROM assistance_requests
        WHERE user_id = ?
        AND escalation = 1
        ORDER BY created_at DESC
        LIMIT ?
        """,
        (
            user_id,
            limit,
        ),
    )

    return [dict(request) for request in requests]


# ==========================================================
# CANCEL EMERGENCY
# ==========================================================

def cancel_emergency_request(
    request_id: int,
    user_id: int,
):
    """
    Cancel an active emergency request belonging
    to the specified driver.
    """

    request = get_emergency_request(
        request_id=request_id,
        user_id=user_id,
    )

    if not request:
        return {
            "success": False,
            "message": "Emergency request not found.",
        }

    if request["status"] in (
        "COMPLETED",
        "CANCELLED",
    ):
        return {
            "success": False,
            "message": "Emergency request is already closed.",
        }

    try:

        execute_query(
            """
            UPDATE assistance_requests
            SET
                status = 'CANCELLED',
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            AND user_id = ?
            """,
            (
                request_id,
                user_id,
            ),
        )

        return {
            "success": True,
            "message": "Emergency request cancelled successfully.",
            "request_id": request_id,
        }

    except Exception as error:
        return {
            "success": False,
            "message": f"Emergency cancellation failed: {error}",
        }


# ==========================================================
# EMERGENCY STATUS
# ==========================================================

def get_emergency_status(
    request_id: int,
    user_id: int,
):
    """
    Return a simple status response for an emergency request.
    """

    request = get_emergency_request(
        request_id=request_id,
        user_id=user_id,
    )

    if not request:
        return {
            "success": False,
            "message": "Emergency request not found.",
        }

    return {
        "success": True,
        "request_id": request["id"],
        "status": request["status"],
        "priority": request["priority"],
        "escalation": bool(request["escalation"]),
        "safe_to_drive": bool(request["safe_to_drive"]),
    }


# ==========================================================
# TEST
# ==========================================================

if __name__ == "__main__":

    print("=" * 60)
    print("RSA DRIVER EMERGENCY MODULE TEST")
    print("=" * 60)

    # ------------------------------------------------------
    # Create temporary test user
    # ------------------------------------------------------

    test_email = "emergency_test@rsa.com"

    execute_query(
        "DELETE FROM users WHERE email = ?",
        (test_email,),
    )

    user_id = execute_query(
        """
        INSERT INTO users (
            name,
            email,
            password_hash,
            role
        )
        VALUES (?, ?, ?, ?)
        """,
        (
            "Emergency Test Driver",
            test_email,
            "test_hash",
            "driver",
        ),
    )

    # ------------------------------------------------------
    # Validation
    # ------------------------------------------------------

    validation = validate_emergency_data(
        user_id=user_id,
        incident_type="Accident",
        description="Vehicle involved in an accident.",
        latitude=17.3850,
        longitude=78.4867,
    )

    print(
        "Validation        :",
        "PASS" if validation["success"] else "FAIL"
    )

    # ------------------------------------------------------
    # Create emergency
    # ------------------------------------------------------

    result = create_emergency_request(
        user_id=user_id,
        incident_type="Accident",
        description="Vehicle involved in an accident.",
        latitude=17.3850,
        longitude=78.4867,
    )

    print(
        "Create emergency  :",
        "PASS" if result["success"] else "FAIL"
    )

    request_id = result.get("request_id")

    # ------------------------------------------------------
    # Active emergency
    # ------------------------------------------------------

    active = get_active_emergency(user_id)

    print(
        "Active emergency  :",
        "PASS"
        if active
        and active["id"] == request_id
        and active["escalation"] == 1
        else "FAIL"
    )

    # ------------------------------------------------------
    # Get emergency
    # ------------------------------------------------------

    emergency = get_emergency_request(
        request_id=request_id,
        user_id=user_id,
    )

    print(
        "Get emergency     :",
        "PASS"
        if emergency
        and emergency["priority"] == "CRITICAL"
        else "FAIL"
    )

    # ------------------------------------------------------
    # Emergency history
    # ------------------------------------------------------

    history = get_emergency_history(user_id)

    print(
        "Emergency history :",
        "PASS" if len(history) == 1 else "FAIL"
    )

    # ------------------------------------------------------
    # Status
    # ------------------------------------------------------

    status = get_emergency_status(
        request_id=request_id,
        user_id=user_id,
    )

    print(
        "Emergency status  :",
        "PASS"
        if status["success"]
        and status["status"] == EMERGENCY_STATUS
        else "FAIL"
    )

    # ------------------------------------------------------
    # Cancel
    # ------------------------------------------------------

    cancelled = cancel_emergency_request(
        request_id=request_id,
        user_id=user_id,
    )

    print(
        "Cancel emergency  :",
        "PASS" if cancelled["success"] else "FAIL"
    )

    # ------------------------------------------------------
    # Verify cancellation
    # ------------------------------------------------------

    cancelled_request = get_emergency_request(
        request_id=request_id,
        user_id=user_id,
    )

    print(
        "Cancellation check:",
        "PASS"
        if cancelled_request
        and cancelled_request["status"] == "CANCELLED"
        else "FAIL"
    )

    # ------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------

    execute_query(
        "DELETE FROM users WHERE email = ?",
        (test_email,),
    )

    print("=" * 60)
    print("RSA DRIVER EMERGENCY TEST COMPLETE")
    print("=" * 60)