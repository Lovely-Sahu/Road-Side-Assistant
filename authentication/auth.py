"""
RSA Authentication Core

Handles:
- User registration
- User lookup
- Login
- Password verification
- Role management
- Active-user validation
"""

from database.database import execute_query, fetch_one
from .password import hash_password, verify_password


VALID_ROLES = {
    "driver",
    "provider",
    "admin",
}


def normalize_email(email: str) -> str:
    """Normalize an email address."""

    if not isinstance(email, str):
        raise ValueError("Email must be a string.")

    email = email.strip().lower()

    if not email:
        raise ValueError("Email cannot be empty.")

    return email


def validate_role(role: str) -> str:
    """Validate and normalize a user role."""

    if not isinstance(role, str):
        raise ValueError("Role must be a string.")

    role = role.strip().lower()

    if role not in VALID_ROLES:
        raise ValueError(
            f"Invalid role. Allowed roles: {', '.join(sorted(VALID_ROLES))}"
        )

    return role


def get_user_by_email(email: str):
    """Return a user by email."""

    email = normalize_email(email)

    return fetch_one(
        """
        SELECT
            id,
            name,
            email,
            phone,
            password_hash,
            role,
            is_active,
            created_at
        FROM users
        WHERE email = ?
        """,
        (email,),
    )


def get_user_by_id(user_id: int):
    """Return a user by ID."""

    return fetch_one(
        """
        SELECT
            id,
            name,
            email,
            phone,
            password_hash,
            role,
            is_active,
            created_at
        FROM users
        WHERE id = ?
        """,
        (user_id,),
    )


def register_user(
    name: str,
    email: str,
    password: str,
    phone: str = None,
    role: str = "driver",
):
    """
    Register a new RSA user.

    Returns:
        {
            "success": True,
            "user_id": ...,
            "message": ...
        }

    or

        {
            "success": False,
            "message": ...
        }
    """

    try:
        name = name.strip()
        email = normalize_email(email)
        role = validate_role(role)

        if not name:
            return {
                "success": False,
                "message": "Name cannot be empty.",
            }

        if not isinstance(password, str) or len(password) < 8:
            return {
                "success": False,
                "message": "Password must contain at least 8 characters.",
            }

        existing_user = get_user_by_email(email)

        if existing_user:
            return {
                "success": False,
                "message": "An account with this email already exists.",
            }

        password_hash = hash_password(password)

        user_id = execute_query(
            """
            INSERT INTO users (
                name,
                email,
                phone,
                password_hash,
                role
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                name,
                email,
                phone.strip() if isinstance(phone, str) else phone,
                password_hash,
                role,
            ),
        )

        return {
            "success": True,
            "user_id": user_id,
            "message": "User registered successfully.",
        }

    except ValueError as error:
        return {
            "success": False,
            "message": str(error),
        }

    except Exception as error:
        # Callers log this; the web layer shows users a generic message.
        if "UNIQUE constraint failed: users.phone" in str(error):
            return {
                "success": False,
                "message": "An account with this phone number already exists.",
            }
        return {
            "success": False,
            "message": f"Registration failed: {error}",
        }


def login_user(email: str, password: str):
    """
    Authenticate a user.

    Returns user information without exposing
    the stored password hash.
    """

    try:
        email = normalize_email(email)

        user = get_user_by_email(email)

        if not user:
            return {
                "success": False,
                "message": "Invalid email or password.",
            }

        # Verify the password BEFORE revealing the account state, so the
        # "inactive" message cannot be used to discover registered emails.
        if not verify_password(
            password,
            user["password_hash"],
        ):
            return {
                "success": False,
                "message": "Invalid email or password.",
            }

        if not user["is_active"]:
            return {
                "success": False,
                "message": "This account is inactive. Contact an administrator.",
            }

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
                "created_at": user["created_at"],
            },
        }

    except Exception:
        return {
            "success": False,
            "message": "Authentication failed.",
        }


def is_user_active(user_id: int) -> bool:
    """Check whether a user account is active."""

    user = fetch_one(
        """
        SELECT is_active
        FROM users
        WHERE id = ?
        """,
        (user_id,),
    )

    if not user:
        return False

    return bool(user["is_active"])


def get_user_role(user_id: int):
    """Return the user's role."""

    user = fetch_one(
        """
        SELECT role
        FROM users
        WHERE id = ?
        """,
        (user_id,),
    )

    if not user:
        return None

    return user["role"]


if __name__ == "__main__":

    print("=" * 60)
    print("RSA AUTHENTICATION CORE TEST")
    print("=" * 60)

    test_email = "rsa_test_user@example.com"

    # Clean up a previous test account if it exists.
    existing_user = get_user_by_email(test_email)

    if existing_user:
        from database.database import execute_query

        execute_query(
            "DELETE FROM users WHERE email = ?",
            (test_email,),
        )

    # ----------------------------------------------------------
    # Registration
    # ----------------------------------------------------------

    registration = register_user(
        name="RSA Test User",
        email=test_email,
        password="RSA_Test@123",
        phone="9999999999",
        role="driver",
    )

    print(
        "Registration :",
        "PASS" if registration["success"] else "FAIL"
    )

    # ----------------------------------------------------------
    # Login
    # ----------------------------------------------------------

    login = login_user(
        test_email,
        "RSA_Test@123",
    )

    print(
        "Valid login  :",
        "PASS" if login["success"] else "FAIL"
    )

    # ----------------------------------------------------------
    # Wrong password
    # ----------------------------------------------------------

    wrong_login = login_user(
        test_email,
        "WrongPassword",
    )

    print(
        "Wrong login   :",
        "PASS" if not wrong_login["success"] else "FAIL"
    )

    # ----------------------------------------------------------
    # Role
    # ----------------------------------------------------------

    if registration["success"]:

        role = get_user_role(
            registration["user_id"]
        )

        print(
            "Role check    :",
            "PASS" if role == "driver" else "FAIL"
        )

        print(
            "Active check  :",
            "PASS"
            if is_user_active(registration["user_id"])
            else "FAIL"
        )

    # ----------------------------------------------------------
    # Cleanup
    # ----------------------------------------------------------

    execute_query(
        "DELETE FROM users WHERE email = ?",
        (test_email,),
    )

    print("=" * 60)
    print("RSA AUTHENTICATION TEST COMPLETE")
    print("=" * 60)