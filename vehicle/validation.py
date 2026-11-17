"""
RSA Vehicle Validation

Handles validation and normalization of vehicle information.
"""


def validate_registration_number(registration_number: str) -> str:
    """Validate and normalize a vehicle registration number."""

    if not isinstance(registration_number, str):
        raise ValueError("Registration number must be a string.")

    registration_number = registration_number.strip().upper()

    if not registration_number:
        raise ValueError("Registration number cannot be empty.")

    if len(registration_number) < 4:
        raise ValueError("Invalid registration number.")

    return registration_number


def validate_vehicle_data(
    registration_number: str,
    make: str = None,
    model: str = None,
    year: int = None,
    fuel_type: str = None,
):
    """Validate vehicle information before storing it."""

    try:
        registration_number = validate_registration_number(
            registration_number
        )

        if make is not None:
            if not isinstance(make, str) or not make.strip():
                return {
                    "success": False,
                    "message": "Vehicle make cannot be empty."
                }

        if model is not None:
            if not isinstance(model, str) or not model.strip():
                return {
                    "success": False,
                    "message": "Vehicle model cannot be empty."
                }

        if year is not None:
            try:
                year = int(year)
            except (ValueError, TypeError):
                return {
                    "success": False,
                    "message": "Vehicle year must be a number."
                }

            if year < 1900 or year > 2100:
                return {
                    "success": False,
                    "message": "Invalid vehicle year."
                }

        if fuel_type is not None:
            if not isinstance(fuel_type, str) or not fuel_type.strip():
                return {
                    "success": False,
                    "message": "Fuel type cannot be empty."
                }

        return {
            "success": True,
            "message": "Vehicle data is valid.",
            "data": {
                "registration_number": registration_number,
                "make": make.strip() if isinstance(make, str) else make,
                "model": model.strip() if isinstance(model, str) else model,
                "year": year,
                "fuel_type": (
                    fuel_type.strip().lower()
                    if isinstance(fuel_type, str)
                    else fuel_type
                ),
            }
        }

    except ValueError as error:
        return {
            "success": False,
            "message": str(error)
        }


if __name__ == "__main__":

    print("=" * 60)
    print("RSA VEHICLE VALIDATION TEST")
    print("=" * 60)

    valid = validate_vehicle_data(
        registration_number="AP09AB1234",
        make="Toyota",
        model="Innova",
        year=2022,
        fuel_type="Diesel"
    )

    print(
        "Valid vehicle :",
        "PASS" if valid["success"] else "FAIL"
    )

    invalid = validate_vehicle_data(
        registration_number="",
        make="Toyota",
        model="Innova",
        year=2022,
        fuel_type="Diesel"
    )

    print(
        "Invalid vehicle :",
        "PASS" if not invalid["success"] else "FAIL"
    )

    print("=" * 60)
    print("RSA VEHICLE VALIDATION TEST COMPLETE")
    print("=" * 60)