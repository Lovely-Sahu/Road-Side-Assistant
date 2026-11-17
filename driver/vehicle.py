"""
RSA Driver Vehicle Module
-------------------------
Handles driver vehicle registration, retrieval, update,
and deletion.
"""

from database.database import (
    execute_query,
    fetch_one,
    fetch_all,
)


# ==========================================================
# VALIDATION
# ==========================================================

def validate_vehicle_data(
    registration_number: str,
    make: str = None,
    model: str = None,
    year: int = None,
    fuel_type: str = None,
):
    """
    Validate vehicle information before database insertion.
    """

    if (
        not isinstance(registration_number, str)
        or not registration_number.strip()
    ):
        return {
            "success": False,
            "message": "Registration number is required.",
        }

    if year is not None:
        try:
            year = int(year)
        except (TypeError, ValueError):
            return {
                "success": False,
                "message": "Vehicle year must be a valid number.",
            }

        if year < 1886 or year > 2100:
            return {
                "success": False,
                "message": "Vehicle year is invalid.",
            }

    return {
        "success": True,
        "message": "Vehicle data is valid.",
    }


# ==========================================================
# ADD VEHICLE
# ==========================================================

def add_vehicle(
    user_id: int,
    registration_number: str,
    make: str = None,
    model: str = None,
    year: int = None,
    fuel_type: str = None,
):
    """
    Add a vehicle for a driver.
    """

    validation = validate_vehicle_data(
        registration_number,
        make,
        model,
        year,
        fuel_type,
    )

    if not validation["success"]:
        return validation

    if not user_id:
        return {
            "success": False,
            "message": "User ID is required.",
        }

    registration_number = registration_number.strip().upper()

    existing = fetch_one(
        """
        SELECT id
        FROM vehicles
        WHERE registration_number = ?
        """,
        (registration_number,),
    )

    if existing:
        return {
            "success": False,
            "message": "A vehicle with this registration number already exists.",
        }

    try:
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
                registration_number,
                make.strip() if isinstance(make, str) else make,
                model.strip() if isinstance(model, str) else model,
                year,
                fuel_type.strip()
                if isinstance(fuel_type, str)
                else fuel_type,
            ),
        )

        return {
            "success": True,
            "message": "Vehicle added successfully.",
            "vehicle_id": vehicle_id,
        }

    except Exception as error:
        return {
            "success": False,
            "message": f"Vehicle registration failed: {error}",
        }


# ==========================================================
# GET VEHICLE
# ==========================================================

def get_vehicle(vehicle_id: int):
    """
    Return one vehicle by ID.
    """

    vehicle = fetch_one(
        """
        SELECT
            id,
            user_id,
            registration_number,
            make,
            model,
            year,
            fuel_type,
            created_at
        FROM vehicles
        WHERE id = ?
        """,
        (vehicle_id,),
    )

    if not vehicle:
        return None

    return dict(vehicle)


# ==========================================================
# GET DRIVER VEHICLES
# ==========================================================

def get_driver_vehicles(user_id: int):
    """
    Return all vehicles belonging to a driver.
    """

    vehicles = fetch_all(
        """
        SELECT
            id,
            user_id,
            registration_number,
            make,
            model,
            year,
            fuel_type,
            created_at
        FROM vehicles
        WHERE user_id = ?
        ORDER BY created_at DESC
        """,
        (user_id,),
    )

    return [dict(vehicle) for vehicle in vehicles]


# ==========================================================
# UPDATE VEHICLE
# ==========================================================

def update_vehicle(
    vehicle_id: int,
    registration_number: str = None,
    make: str = None,
    model: str = None,
    year: int = None,
    fuel_type: str = None,
):
    """
    Update vehicle information.
    """

    vehicle = get_vehicle(vehicle_id)

    if not vehicle:
        return {
            "success": False,
            "message": "Vehicle not found.",
        }

    if registration_number is not None:
        if not isinstance(registration_number, str):
            return {
                "success": False,
                "message": "Registration number must be a string.",
            }

        registration_number = registration_number.strip().upper()

        if not registration_number:
            return {
                "success": False,
                "message": "Registration number cannot be empty.",
            }

        duplicate = fetch_one(
            """
            SELECT id
            FROM vehicles
            WHERE registration_number = ?
            AND id != ?
            """,
            (
                registration_number,
                vehicle_id,
            ),
        )

        if duplicate:
            return {
                "success": False,
                "message": "Another vehicle already uses this registration number.",
            }

    if year is not None:
        try:
            year = int(year)
        except (TypeError, ValueError):
            return {
                "success": False,
                "message": "Vehicle year must be a valid number.",
            }

        if year < 1886 or year > 2100:
            return {
                "success": False,
                "message": "Vehicle year is invalid.",
            }

    try:
        execute_query(
            """
            UPDATE vehicles
            SET
                registration_number = COALESCE(?, registration_number),
                make = COALESCE(?, make),
                model = COALESCE(?, model),
                year = COALESCE(?, year),
                fuel_type = COALESCE(?, fuel_type)
            WHERE id = ?
            """,
            (
                registration_number,
                make.strip() if isinstance(make, str) else make,
                model.strip() if isinstance(model, str) else model,
                year,
                fuel_type.strip()
                if isinstance(fuel_type, str)
                else fuel_type,
                vehicle_id,
            ),
        )

        return {
            "success": True,
            "message": "Vehicle updated successfully.",
            "vehicle": get_vehicle(vehicle_id),
        }

    except Exception as error:
        return {
            "success": False,
            "message": f"Vehicle update failed: {error}",
        }


# ==========================================================
# DELETE VEHICLE
# ==========================================================

def delete_vehicle(vehicle_id: int):
    """
    Delete a vehicle by ID.
    """

    vehicle = get_vehicle(vehicle_id)

    if not vehicle:
        return {
            "success": False,
            "message": "Vehicle not found.",
        }

    try:
        execute_query(
            """
            DELETE FROM vehicles
            WHERE id = ?
            """,
            (vehicle_id,),
        )

        return {
            "success": True,
            "message": "Vehicle deleted successfully.",
        }

    except Exception as error:
        return {
            "success": False,
            "message": f"Vehicle deletion failed: {error}",
        }


# ==========================================================
# VEHICLE SUMMARY
# ==========================================================

def get_vehicle_summary(user_id: int):
    """
    Return a driver's vehicle summary.
    """

    vehicles = get_driver_vehicles(user_id)

    return {
        "success": True,
        "user_id": user_id,
        "vehicle_count": len(vehicles),
        "vehicles": vehicles,
    }


# ==========================================================
# TEST
# ==========================================================

if __name__ == "__main__":

    print("=" * 60)
    print("RSA DRIVER VEHICLE MODULE TEST")
    print("=" * 60)

    from database.database import execute_query

    test_email = "vehicle_test@rsa.com"

    # ------------------------------------------------------
    # Create temporary test user
    # ------------------------------------------------------

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
            "Vehicle Test User",
            test_email,
            "test_hash",
            "driver",
        ),
    )

    # ------------------------------------------------------
    # Add vehicle
    # ------------------------------------------------------

    result = add_vehicle(
        user_id=user_id,
        registration_number="TS09AB1234",
        make="Toyota",
        model="Innova",
        year=2022,
        fuel_type="Diesel",
    )

    print(
        "Add vehicle       :",
        "PASS" if result["success"] else "FAIL"
    )

    vehicle_id = result.get("vehicle_id")

    # ------------------------------------------------------
    # Get vehicle
    # ------------------------------------------------------

    vehicle = get_vehicle(vehicle_id)

    print(
        "Get vehicle       :",
        "PASS"
        if vehicle
        and vehicle["registration_number"] == "TS09AB1234"
        else "FAIL"
    )

    # ------------------------------------------------------
    # Get driver vehicles
    # ------------------------------------------------------

    vehicles = get_driver_vehicles(user_id)

    print(
        "Driver vehicles   :",
        "PASS" if len(vehicles) == 1 else "FAIL"
    )

    # ------------------------------------------------------
    # Update vehicle
    # ------------------------------------------------------

    updated = update_vehicle(
        vehicle_id=vehicle_id,
        model="Innova Crysta",
    )

    print(
        "Update vehicle    :",
        "PASS" if updated["success"] else "FAIL"
    )

    # ------------------------------------------------------
    # Summary
    # ------------------------------------------------------

    summary = get_vehicle_summary(user_id)

    print(
        "Vehicle summary   :",
        "PASS"
        if summary["vehicle_count"] == 1
        else "FAIL"
    )

    # ------------------------------------------------------
    # Delete vehicle
    # ------------------------------------------------------

    deleted = delete_vehicle(vehicle_id)

    print(
        "Delete vehicle    :",
        "PASS" if deleted["success"] else "FAIL"
    )

    # ------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------

    execute_query(
        "DELETE FROM users WHERE email = ?",
        (test_email,),
    )

    print("=" * 60)
    print("RSA DRIVER VEHICLE TEST COMPLETE")
    print("=" * 60)