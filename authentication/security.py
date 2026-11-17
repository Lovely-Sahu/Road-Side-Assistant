"""
RSA - Authentication Security
-----------------------------
Password hashing and token security utilities.
"""

import base64
import hashlib
import hmac
import json
import secrets
import time
from typing import Optional


# ------------------------------------------------------------------
# SECURITY CONFIGURATION
# ------------------------------------------------------------------

PASSWORD_ITERATIONS = 310_000
SALT_LENGTH = 32
TOKEN_EXPIRY_SECONDS = 60 * 60  # 1 hour

# Token signing key: RSA_SECRET_KEY from the environment; the constant is only a
# development fallback for the console app (the web app never uses these tokens).
import os as _os

SECRET_KEY = _os.environ.get("RSA_SECRET_KEY") or "RSA-DEVELOPMENT-SECRET-CHANGE-IN-PRODUCTION"


# ------------------------------------------------------------------
# PASSWORD HASHING
# ------------------------------------------------------------------

def hash_password(password: str) -> str:
    """
    Securely hash a password using PBKDF2-HMAC-SHA256.

    Stored format:
        pbkdf2_sha256$iterations$salt$hash
    """

    if not isinstance(password, str):
        raise TypeError("Password must be a string.")

    if not password:
        raise ValueError("Password cannot be empty.")

    salt = secrets.token_bytes(SALT_LENGTH)

    password_hash = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        PASSWORD_ITERATIONS
    )

    return (
        f"pbkdf2_sha256$"
        f"{PASSWORD_ITERATIONS}$"
        f"{base64.urlsafe_b64encode(salt).decode()}$"
        f"{base64.urlsafe_b64encode(password_hash).decode()}"
    )


def verify_password(password: str, stored_hash: str) -> bool:
    """
    Verify a password against a previously stored hash.
    """

    if not password or not stored_hash:
        return False

    try:
        algorithm, iterations, salt_encoded, hash_encoded = (
            stored_hash.split("$")
        )

        if algorithm != "pbkdf2_sha256":
            return False

        iterations = int(iterations)

        salt = base64.urlsafe_b64decode(
            salt_encoded.encode("utf-8")
        )

        expected_hash = base64.urlsafe_b64decode(
            hash_encoded.encode("utf-8")
        )

        actual_hash = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt,
            iterations
        )

        return hmac.compare_digest(
            actual_hash,
            expected_hash
        )

    except (ValueError, TypeError, UnicodeError):
        return False


# ------------------------------------------------------------------
# TOKEN HELPERS
# ------------------------------------------------------------------

def _base64_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("utf-8")


def _base64_decode(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(
        (data + padding).encode("utf-8")
    )


def _sign(data: str) -> str:
    signature = hmac.new(
        SECRET_KEY.encode("utf-8"),
        data.encode("utf-8"),
        hashlib.sha256
    ).digest()

    return _base64_encode(signature)


# ------------------------------------------------------------------
# ACCESS TOKEN
# ------------------------------------------------------------------

def create_access_token(
    user_id: int | str,
    email: str,
    role: str = "user",
    expires_in: int = TOKEN_EXPIRY_SECONDS
) -> str:
    """
    Create a signed RSA access token.
    """

    now = int(time.time())

    header = {
        "alg": "HS256",
        "typ": "RSA"
    }

    payload = {
        "sub": str(user_id),
        "email": email,
        "role": role,
        "iat": now,
        "exp": now + expires_in
    }

    header_encoded = _base64_encode(
        json.dumps(
            header,
            separators=(",", ":")
        ).encode("utf-8")
    )

    payload_encoded = _base64_encode(
        json.dumps(
            payload,
            separators=(",", ":")
        ).encode("utf-8")
    )

    message = f"{header_encoded}.{payload_encoded}"

    signature = _sign(message)

    return f"{message}.{signature}"


# ------------------------------------------------------------------
# TOKEN VERIFICATION
# ------------------------------------------------------------------

def decode_access_token(token: str) -> Optional[dict]:
    """
    Verify and decode an RSA access token.

    Returns:
        payload dictionary when valid
        None when invalid/expired
    """

    if not token:
        return None

    try:
        parts = token.split(".")

        if len(parts) != 3:
            return None

        header_encoded, payload_encoded, signature = parts

        message = f"{header_encoded}.{payload_encoded}"

        expected_signature = _sign(message)

        if not hmac.compare_digest(
            signature,
            expected_signature
        ):
            return None

        header = json.loads(
            _base64_decode(header_encoded)
        )

        payload = json.loads(
            _base64_decode(payload_encoded)
        )

        if header.get("alg") != "HS256":
            return None

        if header.get("typ") != "RSA":
            return None

        expiration = payload.get("exp")

        if not expiration:
            return None

        if int(time.time()) >= int(expiration):
            return None

        return payload

    except (
        ValueError,
        TypeError,
        KeyError,
        json.JSONDecodeError,
        UnicodeDecodeError
    ):
        return None


# ------------------------------------------------------------------
# TOKEN USER INFORMATION
# ------------------------------------------------------------------

def get_user_from_token(token: str) -> Optional[dict]:
    """
    Extract authenticated user information from a valid token.
    """

    payload = decode_access_token(token)

    if payload is None:
        return None

    return {
        "user_id": payload.get("sub"),
        "email": payload.get("email"),
        "role": payload.get("role", "user")
    }


# ------------------------------------------------------------------
# TOKEN VALIDATION
# ------------------------------------------------------------------

def is_token_valid(token: str) -> bool:
    """
    Return True only when the token is valid and unexpired.
    """

    return decode_access_token(token) is not None


# ------------------------------------------------------------------
# TEST
# ------------------------------------------------------------------

if __name__ == "__main__":

    print("=" * 60)
    print("RSA SECURITY MODULE TEST")
    print("=" * 60)

    # Password test
    password = "RSA_Test@123"

    hashed = hash_password(password)

    print("Password Hash     :", "PASS")
    print(
        "Correct Password  :",
        "PASS" if verify_password(password, hashed) else "FAIL"
    )
    print(
        "Wrong Password    :",
        "PASS" if not verify_password("WrongPassword", hashed)
        else "FAIL"
    )

    # Token test
    token = create_access_token(
        user_id=1,
        email="test@rsa.com",
        role="user"
    )

    print(
        "Token Created     :",
        "PASS" if token else "FAIL"
    )

    decoded = decode_access_token(token)

    print(
        "Token Validation   :",
        "PASS" if decoded else "FAIL"
    )

    print(
        "User Extraction    :",
        "PASS"
        if decoded
        and decoded.get("email") == "test@rsa.com"
        else "FAIL"
    )

    print(
        "Invalid Token      :",
        "PASS"
        if decode_access_token("invalid.token.value") is None
        else "FAIL"
    )

    print("=" * 60)
    print("RSA SECURITY TEST COMPLETE")
    print("=" * 60)