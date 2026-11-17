"""
RSA configuration
-----------------

All runtime configuration comes from environment variables so development
settings never leak into production and secrets never live in the code.

Development (default):  RSA_ENV unset or "development"
Production:             RSA_ENV=production  (requires RSA_SECRET_KEY, forces
                        secure cookies, disables demo seeding and debug)

See DEPLOYMENT.md for the full list.
"""

import os
import secrets
from dataclasses import dataclass
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
INSTANCE_DIR = Path(os.environ.get("RSA_INSTANCE_DIR", BASE_DIR / "instance")).resolve()


def _flag(name, default=False):
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _int(name, default):
    try:
        return int(os.environ.get(name, default))
    except (TypeError, ValueError):
        return int(default)


@dataclass(frozen=True)
class Settings:
    env: str
    debug: bool
    secret_key: str
    session_cookie_secure: bool
    session_hours: int
    max_upload_mb: int
    max_photos_per_request: int
    upload_dir: Path
    map_tile_url: str
    map_attribution: str
    routing_url: str
    provider_auto_approve: bool
    seed_demo_data: bool
    trust_proxy: bool
    log_level: str
    login_max_failures: int
    login_window_minutes: int

    @property
    def is_production(self):
        return self.env == "production"


def _secret_key(env):
    key = os.environ.get("RSA_SECRET_KEY", "").strip()
    if key:
        if env == "production" and len(key) < 32:
            raise RuntimeError("RSA_SECRET_KEY must be at least 32 characters in production.")
        return key
    if env == "production":
        raise RuntimeError(
            "RSA_SECRET_KEY is not set. Generate one with: "
            "python -c \"import secrets; print(secrets.token_hex(32))\""
        )
    # Development: a random key persisted in instance/ (never committed) so
    # sessions survive restarts without a hard-coded secret in the source.
    INSTANCE_DIR.mkdir(parents=True, exist_ok=True)
    key_file = INSTANCE_DIR / ".dev_secret_key"
    if key_file.exists():
        return key_file.read_text(encoding="utf-8").strip()
    key = secrets.token_hex(32)
    key_file.write_text(key, encoding="utf-8")
    try:
        key_file.chmod(0o600)
    except OSError:
        pass
    return key


def load_settings():
    env = os.environ.get("RSA_ENV", "development").strip().lower() or "development"
    production = env == "production"

    return Settings(
        env=env,
        debug=False if production else _flag("RSA_DEBUG", False),
        secret_key=_secret_key(env),
        session_cookie_secure=True if production else _flag("RSA_SESSION_COOKIE_SECURE", False),
        session_hours=_int("RSA_SESSION_HOURS", 8),
        max_upload_mb=_int("RSA_MAX_UPLOAD_MB", 8),
        max_photos_per_request=_int("RSA_MAX_PHOTOS_PER_REQUEST", 3),
        upload_dir=Path(os.environ.get("RSA_UPLOAD_DIR", INSTANCE_DIR / "uploads")).resolve(),
        map_tile_url=os.environ.get("RSA_MAP_TILE_URL", "https://tile.openstreetmap.org/{z}/{x}/{y}.png"),
        map_attribution=os.environ.get(
            "RSA_MAP_ATTRIBUTION", "&copy; OpenStreetMap contributors"
        ),
        routing_url=os.environ.get("RSA_ROUTING_URL", "").strip().rstrip("/"),
        provider_auto_approve=_flag("RSA_PROVIDER_AUTO_APPROVE", False),
        seed_demo_data=False if production else _flag("RSA_SEED_DEMO_DATA", True),
        trust_proxy=_flag("RSA_TRUST_PROXY", False),
        log_level=os.environ.get("RSA_LOG_LEVEL", "INFO").upper(),
        login_max_failures=_int("RSA_LOGIN_MAX_FAILURES", 5),
        login_window_minutes=_int("RSA_LOGIN_WINDOW_MINUTES", 15),
    )
