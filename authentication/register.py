"""
RSA User Registration Module

Handles registration input validation and delegates
secure account creation to the authentication core.
"""

from .auth import register_user


def validate_registration_data(
    name: str,
    email: str,
    password: str,
    confirm_password: str,
    phone: str = None,
    role: str = "driver",
):
    """
    Validate registration data before creating an account.
    """

    if not isinstance(name, str) or not name.strip():
        return {
            "success": False,
            "message": "Name is required.",
        }

    if not isinstance(email, str) or not email.strip():
        return {
            "success": False,
            "message": "Email is required.",
        }

    if not isinstance(password, str) or not password:
        return {
            "success": False,
            "message": "Password is required.",
        }

    if password != confirm_password:
        return {
            "success": False,
            "message": "Passwords do not match.",
        }

    if len(password) < 8:
        return {
            "success": False,
            "message": "Password must contain at least 8 characters.",
        }

    return {
        "success": True,
        "message": "Registration data is valid.",
    }


def register(
    name: str,
    email: str,
    password: str,
    confirm_password: str,
    phone: str = None,
    role: str = "driver",
):
    """
    Validate and register a new RSA user.
    """

    validation = validate_registration_data(
        name=name,
        email=email,
        password=password,
        confirm_password=confirm_password,
        phone=phone,
        role=role,
    )

    if not validation["success"]:
        return validation

    return register_user(
        name=name,
        email=email,
        password=password,
        phone=phone,
        role=role,
    )


if __name__ == "__main__":

    print("=" * 60)
    print("RSA REGISTRATION MODULE TEST")
    print("=" * 60)

    test_email = "registration_test@example.com"

    # ----------------------------------------------------------
    # Remove previous test account
    # ----------------------------------------------------------

    from database.database import execute_query

    execute_query(
        "DELETE FROM users WHERE email = ?",
        (test_email,),
    )

    # ----------------------------------------------------------
    # Valid registration
    # ----------------------------------------------------------

    result = register(
        name="Registration Test User",
        email=test_email,
        password="RSA_Test@123",
        confirm_password="RSA_Test@123",
        phone="8888888888",
        role="driver",
    )

    print(
        "Valid registration :",
        "PASS" if result["success"] else "FAIL"
    )

    # ----------------------------------------------------------
    # Password mismatch
    # ----------------------------------------------------------

    mismatch = register(
        name="Test User",
        email="mismatch@example.com",
        password="RSA_Test@123",
        confirm_password="DifferentPassword",
        role="driver",
    )

    print(
        "Password mismatch  :",
        "PASS" if not mismatch["success"] else "FAIL"
    )

    # ----------------------------------------------------------
    # Short password
    # ----------------------------------------------------------

    short_password = register(
        name="Test User",
        email="short@example.com",
        password="123",
        confirm_password="123",
        role="driver",
    )

    print(
        "Short password     :",
        "PASS" if not short_password["success"] else "FAIL"
    )

    # ----------------------------------------------------------
    # Duplicate email
    # ----------------------------------------------------------

    duplicate = register(
        name="Another User",
        email=test_email,
        password="RSA_Test@123",
        confirm_password="RSA_Test@123",
        role="driver",
    )

    print(
        "Duplicate email    :",
        "PASS" if not duplicate["success"] else "FAIL"
    )

    # ----------------------------------------------------------
    # Cleanup
    # ----------------------------------------------------------

    execute_query(
        "DELETE FROM users WHERE email = ?",
        (test_email,),
    )

    print("=" * 60)
    print("RSA REGISTRATION TEST COMPLETE")
    print("=" * 60)