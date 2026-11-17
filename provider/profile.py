"""
RSA Provider Profiles
---------------------
Handles provider profile management.

Handles:
- Get provider profile
- Update provider profile
- Provider profile validation
- Profile summary
"""

from database.database import execute_query, fetch_one
from .provider import get_provider_by_id


# ==========================================================
# GET PROFILE
# ==========================================================

def get_profile(provider_id: int):
    """
    Return the complete provider profile.
    """

    if not provider_id:
        return {
            "success": False,
            "message": "Provider ID is required.",
        }

    provider = get_provider_by_id(provider_id)

    if not provider:
        return {
            "success": False,
            "message": "Provider not found.",
        }

    return {
        "success": True,
        "provider": dict(provider),
    }


# ==========================================================
# PROFILE VALIDATION
# ==========================================================

def validate_profile_data(
    business_name: str = None,
    service_type: str = None,
    phone: str = None,
):
    """
    Validate provider profile information.

    Only supplied fields are validated.
    """

    # ------------------------------------------------------
    # Business name
    # ------------------------------------------------------

    if business_name is not None:

        if not isinstance(business_name, str):
            return {
                "success": False,
                "message": "Business name must be a string.",
            }

        if not business_name.strip():
            return {
                "success": False,
                "message": "Business name cannot be empty.",
            }

    # ------------------------------------------------------
    # Service type
    # ------------------------------------------------------

    if service_type is not None:

        if not isinstance(service_type, str):
            return {
                "success": False,
                "message": "Service type must be a string.",
            }

        if not service_type.strip():
            return {
                "success": False,
                "message": "Service type cannot be empty.",
            }

    # ------------------------------------------------------
    # Phone
    # ------------------------------------------------------

    if phone is not None:

        if not isinstance(phone, str):
            return {
                "success": False,
                "message": "Phone must be a string.",
            }

        if not phone.strip():
            return {
                "success": False,
                "message": "Phone cannot be empty.",
            }

    return {
        "success": True,
        "message": "Profile information is valid.",
    }


# ==========================================================
# UPDATE PROFILE
# ==========================================================

def update_profile(
    provider_id: int,
    business_name: str = None,
    service_type: str = None,
    phone: str = None,
):
    """
    Update provider profile information.

    Only supplied fields are updated.
    """

    if not provider_id:
        return {
            "success": False,
            "message": "Provider ID is required.",
        }

    # ------------------------------------------------------
    # Check provider
    # ------------------------------------------------------

    provider = get_provider_by_id(provider_id)

    if not provider:
        return {
            "success": False,
            "message": "Provider not found.",
        }

    # ------------------------------------------------------
    # Validate input
    # ------------------------------------------------------

    validation = validate_profile_data(
        business_name=business_name,
        service_type=service_type,
        phone=phone,
    )

    if not validation["success"]:
        return validation

    # ------------------------------------------------------
    # Build update query
    # ------------------------------------------------------

    updates = []
    parameters = []

    if business_name is not None:

        updates.append(
            "business_name = ?"
        )

        parameters.append(
            business_name.strip()
        )

    if service_type is not None:

        updates.append(
            "service_type = ?"
        )

        parameters.append(
            service_type.strip()
        )

    if phone is not None:

        updates.append(
            "phone = ?"
        )

        parameters.append(
            phone.strip()
        )

    # ------------------------------------------------------
    # Nothing to update
    # ------------------------------------------------------

    if not updates:

        return {
            "success": False,
            "message": "No profile information provided.",
        }

    # ------------------------------------------------------
    # Provider ID
    # ------------------------------------------------------

    parameters.append(provider_id)

    query = f"""
        UPDATE providers
        SET {", ".join(updates)}
        WHERE id = ?
    """

    # ------------------------------------------------------
    # Execute update
    # ------------------------------------------------------

    try:

        execute_query(
            query,
            tuple(parameters),
        )

        updated_provider = get_provider_by_id(
            provider_id
        )

        if not updated_provider:

            return {
                "success": False,
                "message": (
                    "Provider was updated but "
                    "could not be retrieved."
                ),
            }

        return {
            "success": True,
            "message": (
                "Provider profile updated successfully."
            ),
            "provider": dict(updated_provider),
        }

    except Exception as error:

        return {
            "success": False,
            "message": (
                f"Profile update failed: {error}"
            ),
        }


# ==========================================================
# PROFILE SUMMARY
# ==========================================================

def get_profile_summary(provider_id: int):
    """
    Return a simplified provider profile summary.
    """

    if not provider_id:
        return {
            "success": False,
            "message": "Provider ID is required.",
        }

    provider = get_provider_by_id(provider_id)

    if not provider:
        return {
            "success": False,
            "message": "Provider not found.",
        }

    return {
        "success": True,

        "profile": {
            "id": provider["id"],
            "user_id": provider["user_id"],
            "business_name": provider["business_name"],
            "service_type": provider["service_type"],
            "phone": provider["phone"],
            "availability": provider["availability"],
            "rating": provider["rating"],
            "latitude": provider["latitude"],
            "longitude": provider["longitude"],
            "created_at": provider["created_at"],
        },
    }


# ==========================================================
# TEST
# ==========================================================

def run_tests():

    print("=" * 60)
    print("RSA PROVIDER PROFILE TEST")
    print("=" * 60)

    # ------------------------------------------------------
    # Function availability
    # ------------------------------------------------------

    functions = [
        get_profile,
        validate_profile_data,
        update_profile,
        get_profile_summary,
    ]

    print(
        "Module import      : PASS"
    )

    print(
        "Functions loaded   :",
        "PASS"
        if all(callable(function) for function in functions)
        else "FAIL",
    )

    # ------------------------------------------------------
    # Validation test
    # ------------------------------------------------------

    valid = validate_profile_data(
        business_name="Test Provider",
        service_type="Towing",
        phone="9999999999",
    )

    print(
        "Valid profile      :",
        "PASS"
        if valid["success"]
        else "FAIL",
    )

    # ------------------------------------------------------
    # Empty business name
    # ------------------------------------------------------

    invalid_name = validate_profile_data(
        business_name="",
    )

    print(
        "Empty business     :",
        "PASS"
        if not invalid_name["success"]
        else "FAIL",
    )

    # ------------------------------------------------------
    # Empty service
    # ------------------------------------------------------

    invalid_service = validate_profile_data(
        service_type="",
    )

    print(
        "Empty service      :",
        "PASS"
        if not invalid_service["success"]
        else "FAIL",
    )

    # ------------------------------------------------------
    # Empty phone
    # ------------------------------------------------------

    invalid_phone = validate_profile_data(
        phone="",
    )

    print(
        "Empty phone        :",
        "PASS"
        if not invalid_phone["success"]
        else "FAIL",
    )

    # ------------------------------------------------------
    # Missing provider
    # ------------------------------------------------------

    profile = get_profile(999999999)

    print(
        "Missing provider   :",
        "PASS"
        if not profile["success"]
        else "FAIL",
    )

    # ------------------------------------------------------
    # Missing provider summary
    # ------------------------------------------------------

    summary = get_profile_summary(
        999999999
    )

    print(
        "Summary validation :",
        "PASS"
        if not summary["success"]
        else "FAIL",
    )

    # ------------------------------------------------------
    # Missing provider update
    # ------------------------------------------------------

    update = update_profile(
        provider_id=999999999,
        business_name="Test Provider",
    )

    print(
        "Update validation  :",
        "PASS"
        if not update["success"]
        else "FAIL",
    )

    # ------------------------------------------------------
    # Final
    # ------------------------------------------------------

    print("=" * 60)
    print("RSA PROVIDER PROFILE TEST COMPLETE")
    print("=" * 60)


# ==========================================================
# ENTRY POINT
# ==========================================================

if __name__ == "__main__":
    run_tests()