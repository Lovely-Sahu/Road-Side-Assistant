"""
RSA - Login Module
------------------
Handles user login and access-token generation.
"""

from .auth import get_user_by_email
from .security import create_access_token
from .password import verify_password


# ------------------------------------------------------------------
# LOGIN
# ------------------------------------------------------------------

def login_user(email: str, password: str):
    """
    Authenticate a user using email and password.

    Returns:
        {
            "success": True,
            "message": "...",
            "user": {...},
            "access_token": "..."
        }

    or

        {
            "success": False,
            "message": "..."
        }
    """

    if not isinstance(email, str) or not email.strip():
        return {
            "success": False,
            "message": "Email and password are required."
        }

    if not isinstance(password, str) or not password:
        return {
            "success": False,
            "message": "Email and password are required."
        }

    email = email.strip().lower()

    try:
        # ----------------------------------------------------------
        # Find user through the existing authentication core
        # ----------------------------------------------------------

        user = get_user_by_email(email)

        if not user:
            return {
                "success": False,
                "message": "Invalid email or password."
            }

        # ----------------------------------------------------------
        # Password verification
        # ----------------------------------------------------------

        if not verify_password(
            password,
            user["password_hash"]
        ):
            return {
                "success": False,
                "message": "Invalid email or password."
            }

        # Account state is revealed only after the password is verified.
        if not user["is_active"]:
            return {
                "success": False,
                "message": "This account is inactive."
            }

        # ----------------------------------------------------------
        # Generate access token
        # ----------------------------------------------------------

        access_token = create_access_token(
            user_id=user["id"],
            email=user["email"],
            role=user["role"]
        )

        # ----------------------------------------------------------
        # Return authenticated user
        # ----------------------------------------------------------

        return {
            "success": True,
            "message": "Login successful.",
            "user": {
                "id": user["id"],
                "name": user["name"],
                "email": user["email"],
                "phone": user["phone"],
                "role": user["role"],
                "is_active": bool(user["is_active"]),
                "created_at": user["created_at"]
            },
            "access_token": access_token
        }

    except Exception:
        return {
            "success": False,
            "message": "Authentication failed."
        }


# ------------------------------------------------------------------
# TEST
# ------------------------------------------------------------------

if __name__ == "__main__":

    print("=" * 60)
    print("RSA LOGIN MODULE TEST")
    print("=" * 60)

    test_email = "login_test@example.com"
    test_password = "RSA_Test@123"

    # ----------------------------------------------------------
    # Create a test account using the same registration system
    # ----------------------------------------------------------

    from .register import register
    from database.database import execute_query

    # Remove previous test account
    execute_query(
        "DELETE FROM users WHERE email = ?",
        (test_email,)
    )

    registration = register(
        name="Login Test User",
        email=test_email,
        password=test_password,
        confirm_password=test_password,
        phone="9999999999",
        role="driver"
    )

    print(
        "Test registration :",
        "PASS" if registration["success"] else "FAIL"
    )

    # ----------------------------------------------------------
    # Valid login
    # ----------------------------------------------------------

    result = login_user(
        test_email,
        test_password
    )

    print(
        "Valid login       :",
        "PASS" if result["success"] else "FAIL"
    )

    # ----------------------------------------------------------
    # Wrong password
    # ----------------------------------------------------------

    wrong_login = login_user(
        test_email,
        "WrongPassword"
    )

    print(
        "Wrong password     :",
        "PASS"
        if not wrong_login["success"]
        else "FAIL"
    )

    # ----------------------------------------------------------
    # Token generation
    # ----------------------------------------------------------

    if result["success"]:

        print(
            "User returned      :",
            "PASS"
            if result["user"]["email"] == test_email
            else "FAIL"
        )

        print(
            "Role returned      :",
            "PASS"
            if result["user"]["role"] == "driver"
            else "FAIL"
        )

        print(
            "Access token       :",
            "PASS"
            if result.get("access_token")
            else "FAIL"
        )

    # ----------------------------------------------------------
    # Cleanup
    # ----------------------------------------------------------

    execute_query(
        "DELETE FROM users WHERE email = ?",
        (test_email,)
    )

    print("=" * 60)
    print("RSA LOGIN MODULE TEST COMPLETE")
    print("=" * 60)