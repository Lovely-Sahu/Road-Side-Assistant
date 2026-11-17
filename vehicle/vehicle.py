"""
RSA Vehicle Management
----------------------
Handles vehicle registration, retrieval, updating,
deletion, and ownership validation.
"""

from database.database import execute_query, fetch_one, fetch_all


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
    """Validate vehicle information."""

    if not isinstance(registration_number, str):
        return {
            "success": False,
            "message": "Registration number must be a string."
        }

    registration_number = registration_number.strip().upper()

    if not registration_number:
        return {
            "success": False,
            "message": "Registration number is required."
        }

    if year is not None:
        try:
            year = int(year)
        except (ValueError, TypeError):
            return {
                "success": False,
                "message": "Year must be a valid number."
            }

        if year < 1886 or year > 2100:
            return {
                "success": False,
                "message": "Invalid vehicle year."
            }

    return {
        "success": True,
        "message": "Vehicle data is valid."
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
    """Register a vehicle for a user."""

    validation = validate_vehicle_data(
        registration_number,
        make,
        model,
        year,
        fuel_type
    )

    if not validation["success"]:
        return validation

    try:
        registration_number = registration_number.strip().upper()

        # Check whether vehicle already exists.
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
                "message": "A vehicle with this registration number already exists."
            }

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
                fuel_type.strip() if isinstance(fuel_type, str) else fuel_type,
            ),
        )

        return {
            "success": True,
            "vehicle_id": vehicle_id,
            "message": "Vehicle added successfully."
        }

    except Exception as error:
        return {
            "success": False,
            "message": f"Failed to add vehicle: {error}"
        }


# ==========================================================
# GET VEHICLE
# ==========================================================

def get_vehicle(vehicle_id: int, user_id: int = None):
    """
    Get vehicle information.

    If user_id is supplied, ownership is also verified.
    """

    if user_id is not None:

        return fetch_one(
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
              AND user_id = ?
            """,
            (vehicle_id, user_id),
        )

    return fetch_one(
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


# ==========================================================
# GET USER VEHICLES
# ==========================================================

def get_user_vehicles(user_id: int):
    """Return all vehicles belonging to a user."""

    return fetch_all(
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


# ==========================================================
# UPDATE VEHICLE
# ==========================================================

def update_vehicle(
    vehicle_id: int,
    user_id: int,
    registration_number: str = None,
    make: str = None,
    model: str = None,
    year: int = None,
    fuel_type: str = None,
):
    """Update a vehicle belonging to the user."""

    vehicle = get_vehicle(
        vehicle_id=vehicle_id,
        user_id=user_id
    )

    if not vehicle:
        return {
            "success": False,
            "message": "Vehicle not found or access denied."
        }

    if registration_number is not None:
        registration_number = (
            registration_number.strip().upper()
        )

        existing = fetch_one(
            """
            SELECT id
            FROM vehicles
            WHERE registration_number = ?
              AND id != ?
            """,
            (
                registration_number,
                vehicle_id
            ),
        )

        if existing:
            return {
                "success": False,
                "message": "Registration number already belongs to another vehicle."
            }

    if year is not None:
        try:
            year = int(year)
        except (ValueError, TypeError):
            return {
                "success": False,
                "message": "Year must be a valid number."
            }

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
          AND user_id = ?
        """,
        (
            registration_number,
            make.strip() if isinstance(make, str) else make,
            model.strip() if isinstance(model, str) else model,
            year,
            fuel_type.strip() if isinstance(fuel_type, str) else fuel_type,
            vehicle_id,
            user_id,
        ),
    )

    return {
        "success": True,
        "message": "Vehicle updated successfully."
    }


# ==========================================================
# DELETE VEHICLE
# ==========================================================

def delete_vehicle(vehicle_id: int, user_id: int):
    """Delete a vehicle belonging to the user."""

    vehicle = get_vehicle(
        vehicle_id=vehicle_id,
        user_id=user_id
    )

    if not vehicle:
        return {
            "success": False,
            "message": "Vehicle not found or access denied."
        }

    execute_query(
        """
        DELETE FROM vehicles
        WHERE id = ?
          AND user_id = ?
        """,
        (
            vehicle_id,
            user_id
        ),
    )

    return {
        "success": True,
        "message": "Vehicle deleted successfully."
    }


# ==========================================================
# OWNERSHIP CHECK
# ==========================================================

def user_owns_vehicle(
    user_id: int,
    vehicle_id: int
) -> bool:
    """Check whether a vehicle belongs to a user."""

    vehicle = fetch_one(
        """
        SELECT id
        FROM vehicles
        WHERE id = ?
          AND user_id = ?
        """,
        (
            vehicle_id,
            user_id
        ),
    )

    return vehicle is not None


# ==========================================================
# TEST
# ==========================================================

if __name__ == "__main__":

    print("=" * 60)
    print("RSA VEHICLE MANAGEMENT TEST")
    print("=" * 60)

    # ------------------------------------------------------
    # Create a temporary user
    # ------------------------------------------------------

    from database.database import execute_query

    test_email = "vehicle_test@example.com"

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
        registration_number="AP01AB1234",
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

    vehicle = get_vehicle(
        vehicle_id,
        user_id
    )

    print(
        "Get vehicle       :",
        "PASS" if vehicle else "FAIL"
    )

    # ------------------------------------------------------
    # Ownership
    # ------------------------------------------------------

    ownership = user_owns_vehicle(
        user_id,
        vehicle_id
    )

    print(
        "Ownership check   :",
        "PASS" if ownership else "FAIL"
    )

    # ------------------------------------------------------
    # Get all vehicles
    # ------------------------------------------------------

    vehicles = get_user_vehicles(user_id)

    print(
        "Vehicle list      :",
        "PASS" if len(vehicles) >= 1 else "FAIL"
    )

    # ------------------------------------------------------
    # Update vehicle
    # ------------------------------------------------------

    update = update_vehicle(
        vehicle_id=vehicle_id,
        user_id=user_id,
        model="Innova Crysta",
    )

    print(
        "Update vehicle    :",
        "PASS" if update["success"] else "FAIL"
    )

    # ------------------------------------------------------
    # Delete vehicle
    # ------------------------------------------------------

    delete = delete_vehicle(
        vehicle_id,
        user_id
    )

    print(
        "Delete vehicle    :",
        "PASS" if delete["success"] else "FAIL"
    )

    # ------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------

    execute_query(
        "DELETE FROM users WHERE id = ?",
        (user_id,),
    )

    print("=" * 60)
    print("RSA VEHICLE MANAGEMENT TEST COMPLETE")
    print("=" * 60)