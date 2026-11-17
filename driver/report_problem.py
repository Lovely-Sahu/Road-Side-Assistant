"""
RSA Driver Problem Reporting Module
-----------------------------------
Handles driver-reported vehicle problems and creates
assistance requests in the RSA system.

Features:
- Problem validation
- Problem classification
- Assistance request creation
- Problem retrieval
- Problem history
- Problem cancellation
"""

from database.database import (
    execute_query,
    fetch_one,
    fetch_all,
)


# ==========================================================
# PROBLEM TYPES
# ==========================================================

VALID_PROBLEM_TYPES = {
    "ENGINE",
    "BRAKE",
    "TYRE",
    "BATTERY",
    "ELECTRICAL",
    "FUEL",
    "OVERHEATING",
    "ACCIDENT",
    "PUNCTURE",
    "OTHER",
}


VALID_PRIORITIES = {
    "LOW",
    "MEDIUM",
    "HIGH",
    "CRITICAL",
}


# ==========================================================
# NORMALIZATION
# ==========================================================

def normalize_problem_type(problem_type: str):
    """
    Normalize and validate a reported problem type.
    """

    if not isinstance(problem_type, str):
        return None

    problem_type = problem_type.strip().upper()

    if problem_type not in VALID_PROBLEM_TYPES:
        return None

    return problem_type


def normalize_priority(priority: str):
    """
    Normalize and validate request priority.
    """

    if not isinstance(priority, str):
        return None

    priority = priority.strip().upper()

    if priority not in VALID_PRIORITIES:
        return None

    return priority


# ==========================================================
# PRIORITY CALCULATION
# ==========================================================

def calculate_priority(
    problem_type: str,
    safe_to_drive: bool = True,
):
    """
    Calculate a suitable assistance priority.
    """

    problem_type = normalize_problem_type(problem_type)

    if not problem_type:
        return "MEDIUM"

    if not safe_to_drive:
        return "CRITICAL"

    critical_problems = {
        "ACCIDENT",
        "BRAKE",
        "ENGINE",
    }

    high_problems = {
        "OVERHEATING",
        "ELECTRICAL",
        "TYRE",
    }

    if problem_type in critical_problems:
        return "HIGH"

    if problem_type in high_problems:
        return "HIGH"

    return "MEDIUM"


# ==========================================================
# SERVICE RECOMMENDATION
# ==========================================================

def recommend_service(problem_type: str):
    """
    Recommend an appropriate roadside service.
    """

    problem_type = normalize_problem_type(problem_type)

    recommendations = {
        "ENGINE": "Mechanic",
        "BRAKE": "Brake Specialist",
        "TYRE": "Tyre Service",
        "BATTERY": "Battery Assistance",
        "ELECTRICAL": "Auto Electrician",
        "FUEL": "Fuel Delivery",
        "OVERHEATING": "Mechanic",
        "ACCIDENT": "Emergency Recovery",
        "PUNCTURE": "Tyre Service",
        "OTHER": "General Roadside Assistance",
    }

    return recommendations.get(
        problem_type,
        "General Roadside Assistance",
    )


# ==========================================================
# VALIDATION
# ==========================================================

def validate_problem_data(
    user_id: int,
    problem_type: str,
    description: str,
    vehicle_id: int = None,
    safe_to_drive: bool = True,
):
    """
    Validate problem-report information.
    """

    if not user_id:
        return {
            "success": False,
            "message": "User ID is required.",
        }

    normalized_type = normalize_problem_type(problem_type)

    if not normalized_type:
        return {
            "success": False,
            "message": (
                "Invalid problem type. "
                f"Allowed types: {', '.join(sorted(VALID_PROBLEM_TYPES))}"
            ),
        }

    if (
        not isinstance(description, str)
        or not description.strip()
    ):
        return {
            "success": False,
            "message": "Problem description is required.",
        }

    if vehicle_id is not None:
        vehicle = fetch_one(
            """
            SELECT id
            FROM vehicles
            WHERE id = ?
            AND user_id = ?
            """,
            (
                vehicle_id,
                user_id,
            ),
        )

        if not vehicle:
            return {
                "success": False,
                "message": "Vehicle not found for this driver.",
            }

    return {
        "success": True,
        "message": "Problem data is valid.",
    }


# ==========================================================
# REPORT PROBLEM
# ==========================================================

def report_problem(
    user_id: int,
    problem_type: str,
    description: str,
    vehicle_id: int = None,
    safe_to_drive: bool = True,
    priority: str = None,
    latitude: float = None,
    longitude: float = None,
):
    """
    Report a vehicle problem and create an assistance request.
    """

    validation = validate_problem_data(
        user_id=user_id,
        problem_type=problem_type,
        description=description,
        vehicle_id=vehicle_id,
        safe_to_drive=safe_to_drive,
    )

    if not validation["success"]:
        return validation

    problem_type = normalize_problem_type(problem_type)

    if priority is None:
        priority = calculate_priority(
            problem_type,
            safe_to_drive,
        )
    else:
        priority = normalize_priority(priority)

        if not priority:
            return {
                "success": False,
                "message": "Invalid priority.",
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

    recommended_service = recommend_service(problem_type)

    # Unsafe-to-drive problems are escalated.
    escalation = 1 if not safe_to_drive else 0

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
                problem_type,
                description.strip(),
                priority,
                recommended_service,
                escalation,
                1 if safe_to_drive else 0,
                "REQUESTED",
                latitude,
                longitude,
            ),
        )

        return {
            "success": True,
            "message": "Vehicle problem reported successfully.",
            "request_id": request_id,
            "problem_type": problem_type,
            "priority": priority,
            "recommended_service": recommended_service,
            "escalation": bool(escalation),
            "safe_to_drive": bool(safe_to_drive),
        }

    except Exception as error:
        return {
            "success": False,
            "message": f"Problem reporting failed: {error}",
        }


# ==========================================================
# GET REPORTED PROBLEM
# ==========================================================

def get_reported_problem(
    request_id: int,
    user_id: int = None,
):
    """
    Return a reported problem / assistance request.
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
# PROBLEM HISTORY
# ==========================================================

def get_problem_history(
    user_id: int,
    limit: int = 10,
):
    """
    Return previous problem reports for a driver.
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
# CANCEL PROBLEM REQUEST
# ==========================================================

def cancel_problem_report(
    request_id: int,
    user_id: int,
):
    """
    Cancel an active problem report.
    """

    request = get_reported_problem(
        request_id=request_id,
        user_id=user_id,
    )

    if not request:
        return {
            "success": False,
            "message": "Problem report not found.",
        }

    if request["status"] in (
        "COMPLETED",
        "CANCELLED",
    ):
        return {
            "success": False,
            "message": "Problem report is already closed.",
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
            "message": "Problem report cancelled successfully.",
            "request_id": request_id,
        }

    except Exception as error:
        return {
            "success": False,
            "message": f"Problem cancellation failed: {error}",
        }


# ==========================================================
# PROBLEM STATUS
# ==========================================================

def get_problem_status(
    request_id: int,
    user_id: int,
):
    """
    Return the current status of a problem report.
    """

    request = get_reported_problem(
        request_id=request_id,
        user_id=user_id,
    )

    if not request:
        return {
            "success": False,
            "message": "Problem report not found.",
        }

    return {
        "success": True,
        "request_id": request["id"],
        "problem_type": request["incident_type"],
        "priority": request["priority"],
        "recommended_service": request["recommended_service"],
        "status": request["status"],
        "escalation": bool(request["escalation"]),
        "safe_to_drive": bool(request["safe_to_drive"]),
    }


# ==========================================================
# TEST
# ==========================================================

if __name__ == "__main__":

    print("=" * 60)
    print("RSA DRIVER PROBLEM REPORTING TEST")
    print("=" * 60)

    test_email = "problem_test@rsa.com"

    # ------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------

    execute_query(
        "DELETE FROM users WHERE email = ?",
        (test_email,),
    )

    # ------------------------------------------------------
    # Create test driver
    # ------------------------------------------------------

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
            "Problem Test Driver",
            test_email,
            "test_hash",
            "driver",
        ),
    )

    # ------------------------------------------------------
    # Create test vehicle
    # ------------------------------------------------------

    vehicle_id = execute_query(
        """
        INSERT INTO vehicles (
            user_id,
            registration_number,
            make,
            model,
            year,
            fuel_type
        )
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            user_id,
            "TS09PROB01",
            "Honda",
            "City",
            2022,
            "Petrol",
        ),
    )

    # ------------------------------------------------------
    # Validation
    # ------------------------------------------------------

    validation = validate_problem_data(
        user_id=user_id,
        problem_type="battery",
        description="Battery is completely dead.",
        vehicle_id=vehicle_id,
        safe_to_drive=False,
    )

    print(
        "Validation        :",
        "PASS" if validation["success"] else "FAIL"
    )

    # ------------------------------------------------------
    # Problem type
    # ------------------------------------------------------

    problem_type = normalize_problem_type("battery")

    print(
        "Problem type      :",
        "PASS" if problem_type == "BATTERY" else "FAIL"
    )

    # ------------------------------------------------------
    # Service
    # ------------------------------------------------------

    service = recommend_service("battery")

    print(
        "Service recommend :",
        "PASS"
        if service == "Battery Assistance"
        else "FAIL"
    )

    # ------------------------------------------------------
    # Priority
    # ------------------------------------------------------

    calculated_priority = calculate_priority(
        "battery",
        safe_to_drive=False,
    )

    print(
        "Priority          :",
        "PASS"
        if calculated_priority == "CRITICAL"
        else "FAIL"
    )

    # ------------------------------------------------------
    # Report problem
    # ------------------------------------------------------

    result = report_problem(
        user_id=user_id,
        problem_type="battery",
        description="Battery is completely dead.",
        vehicle_id=vehicle_id,
        safe_to_drive=False,
        latitude=17.3850,
        longitude=78.4867,
    )

    print(
        "Report problem    :",
        "PASS" if result["success"] else "FAIL"
    )

    request_id = result.get("request_id")

    # ------------------------------------------------------
    # Get report
    # ------------------------------------------------------

    report = get_reported_problem(
        request_id=request_id,
        user_id=user_id,
    )

    print(
        "Get report        :",
        "PASS"
        if report
        and report["incident_type"] == "BATTERY"
        else "FAIL"
    )

    # ------------------------------------------------------
    # History
    # ------------------------------------------------------

    history = get_problem_history(user_id)

    print(
        "Problem history   :",
        "PASS" if len(history) == 1 else "FAIL"
    )

    # ------------------------------------------------------
    # Status
    # ------------------------------------------------------

    status = get_problem_status(
        request_id=request_id,
        user_id=user_id,
    )

    print(
        "Problem status    :",
        "PASS"
        if status["success"]
        and status["status"] == "REQUESTED"
        else "FAIL"
    )

    # ------------------------------------------------------
    # Cancel
    # ------------------------------------------------------

    cancelled = cancel_problem_report(
        request_id=request_id,
        user_id=user_id,
    )

    print(
        "Cancel report     :",
        "PASS" if cancelled["success"] else "FAIL"
    )

    # ------------------------------------------------------
    # Verify cancellation
    # ------------------------------------------------------

    cancelled_report = get_reported_problem(
        request_id=request_id,
        user_id=user_id,
    )

    print(
        "Cancellation check:",
        "PASS"
        if cancelled_report
        and cancelled_report["status"] == "CANCELLED"
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
    print("RSA DRIVER PROBLEM REPORTING TEST COMPLETE")
    print("=" * 60)