"""
RSA Authentication Package

Provides authentication, registration,
password security, and access-token utilities.
"""

from .auth import (
    register_user,
    login_user as core_login_user,
    get_user_by_email,
    get_user_by_id,
    is_user_active,
    get_user_role,
)

from .register import register

from .login import login_user

from .password import (
    hash_password,
    verify_password,
)

from .security import (
    create_access_token,
    decode_access_token,
    get_user_from_token,
    is_token_valid,
)


__all__ = [
    "register_user",
    "core_login_user",
    "get_user_by_email",
    "get_user_by_id",
    "is_user_active",
    "get_user_role",
    "register",
    "login_user",
    "hash_password",
    "verify_password",
    "create_access_token",
    "decode_access_token",
    "get_user_from_token",
    "is_token_valid",
]