"""
RSA Password Security

Handles secure password hashing and verification.
"""

import hashlib
import secrets


def hash_password(password: str) -> str:
    """
    Hash a password using PBKDF2-HMAC-SHA256.

    The returned value contains:
        algorithm$salt$hash
    """

    if not isinstance(password, str) or not password:
        raise ValueError("Password must be a non-empty string.")

    salt = secrets.token_bytes(16)

    password_hash = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        100_000
    )

    return (
        "pbkdf2_sha256$"
        + salt.hex()
        + "$"
        + password_hash.hex()
    )


def verify_password(password: str, stored_hash: str) -> bool:
    """
    Verify a password against a stored password hash.
    """

    try:
        algorithm, salt_hex, hash_hex = stored_hash.split("$")

        if algorithm != "pbkdf2_sha256":
            return False

        salt = bytes.fromhex(salt_hex)

        expected_hash = bytes.fromhex(hash_hex)

        password_hash = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt,
            100_000
        )

        return secrets.compare_digest(
            password_hash,
            expected_hash
        )

    except (ValueError, TypeError):
        return False


if __name__ == "__main__":

    print("=" * 60)
    print("RSA PASSWORD SECURITY TEST")
    print("=" * 60)

    test_password = "RSA_Test@123"

    hashed = hash_password(test_password)

    print("Password hashing : PASS")
    print("Hash generated   :", hashed[:35] + "...")

    correct = verify_password(
        test_password,
        hashed
    )

    incorrect = verify_password(
        "WrongPassword",
        hashed
    )

    print("Correct password :", "PASS" if correct else "FAIL")
    print("Wrong password   :", "PASS" if not incorrect else "FAIL")

    print("=" * 60)