"""
RSA Driver History Module
-------------------------
Handles retrieval of a driver's assistance request history.
"""

from database.database import get_connection


# ------------------------------------------------------------------
# GET DRIVER HISTORY
# ------------------------------------------------------------------

def get_driver_history(user_id: int):
    """
    Return all assistance requests belonging to a driver.

    Returns:
        {
            "success": True,
            "history": [...]
        }

        or

        {
            "success": False,
            "message": "..."
        }
    """

    if not user_id:
        return {
            "success": False,
            "message": "User ID is required.",
        }

    connection = get_connection()

    try:
        cursor = connection.cursor()

        cursor.execute(
            """
            SELECT
                ar.id,
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
                ar.updated_at
            FROM assistance_requests ar
            WHERE ar.user_id = ?
            ORDER BY ar.created_at DESC
            """,
            (user_id,),
        )

        rows = cursor.fetchall()

        history = []

        for row in rows:
            history.append({
                "id": row["id"],
                "vehicle_id": row["vehicle_id"],
                "incident_type": row["incident_type"],
                "description": row["description"],
                "priority": row["priority"],
                "recommended_service": row["recommended_service"],
                "escalation": bool(row["escalation"]),
                "safe_to_drive": bool(row["safe_to_drive"]),
                "status": row["status"],
                "latitude": row["latitude"],
                "longitude": row["longitude"],
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
            })

        return {
            "success": True,
            "history": history,
        }

    except Exception as error:
        return {
            "success": False,
            "message": f"Unable to retrieve history: {error}",
        }

    finally:
        connection.close()


# ------------------------------------------------------------------
# GET SINGLE HISTORY RECORD
# ------------------------------------------------------------------

def get_history_record(
    user_id: int,
    request_id: int,
):
    """
    Retrieve one assistance request from a driver's history.
    """

    if not user_id or not request_id:
        return {
            "success": False,
            "message": "User ID and request ID are required.",
        }

    connection = get_connection()

    try:
        cursor = connection.cursor()

        cursor.execute(
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
            WHERE id = ?
              AND user_id = ?
            """,
            (request_id, user_id),
        )

        row = cursor.fetchone()

        if row is None:
            return {
                "success": False,
                "message": "History record not found.",
            }

        return {
            "success": True,
            "record": {
                "id": row["id"],
                "vehicle_id": row["vehicle_id"],
                "incident_type": row["incident_type"],
                "description": row["description"],
                "priority": row["priority"],
                "recommended_service": row["recommended_service"],
                "escalation": bool(row["escalation"]),
                "safe_to_drive": bool(row["safe_to_drive"]),
                "status": row["status"],
                "latitude": row["latitude"],
                "longitude": row["longitude"],
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
            },
        }

    except Exception as error:
        return {
            "success": False,
            "message": f"Unable to retrieve record: {error}",
        }

    finally:
        connection.close()


# ------------------------------------------------------------------
# HISTORY SUMMARY
# ------------------------------------------------------------------

def get_history_summary(user_id: int):
    """
    Return a summary of the driver's assistance history.
    """

    if not user_id:
        return {
            "success": False,
            "message": "User ID is required.",
        }

    connection = get_connection()

    try:
        cursor = connection.cursor()

        cursor.execute(
            """
            SELECT
                COUNT(*) AS total_requests,
                SUM(
                    CASE
                        WHEN status = 'COMPLETED'
                        THEN 1
                        ELSE 0
                    END
                ) AS completed_requests,
                SUM(
                    CASE
                        WHEN status = 'CANCELLED'
                        THEN 1
                        ELSE 0
                    END
                ) AS cancelled_requests,
                SUM(
                    CASE
                        WHEN status IN ('REQUESTED', 'MATCHED', 'IN_PROGRESS')
                        THEN 1
                        ELSE 0
                    END
                ) AS active_requests
            FROM assistance_requests
            WHERE user_id = ?
            """,
            (user_id,),
        )

        row = cursor.fetchone()

        return {
            "success": True,
            "summary": {
                "total_requests": row["total_requests"] or 0,
                "completed_requests": row["completed_requests"] or 0,
                "cancelled_requests": row["cancelled_requests"] or 0,
                "active_requests": row["active_requests"] or 0,
            },
        }

    except Exception as error:
        return {
            "success": False,
            "message": f"Unable to retrieve history summary: {error}",
        }

    finally:
        connection.close()


# ------------------------------------------------------------------
# TEST
# ------------------------------------------------------------------

if __name__ == "__main__":

    print("=" * 60)
    print("RSA DRIVER HISTORY TEST")
    print("=" * 60)

    # Test with user ID 1.
    test_user_id = 1

    history = get_driver_history(test_user_id)

    print(
        "History retrieval :",
        "PASS" if history["success"] else "FAIL"
    )

    if history["success"]:
        print(
            "Records found     :",
            len(history["history"])
        )

    summary = get_history_summary(test_user_id)

    print(
        "History summary    :",
        "PASS" if summary["success"] else "FAIL"
    )

    if summary["success"]:
        print(
            "Total requests    :",
            summary["summary"]["total_requests"]
        )

    print("=" * 60)
    print("RSA DRIVER HISTORY TEST COMPLETE")
    print("=" * 60)