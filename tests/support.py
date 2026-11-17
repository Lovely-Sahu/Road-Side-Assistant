"""
Shared test setup.

Every test runs against a temporary SQLite database created for that test
(RSA_DATABASE_PATH points at a temp file), so the real rsa.db is never opened,
modified or cleaned up by the test suite.
"""

import atexit
import os
import shutil
import sqlite3
import tempfile
from pathlib import Path

_ROOT = Path(tempfile.mkdtemp(prefix="rsa-tests-"))
atexit.register(shutil.rmtree, _ROOT, True)

os.environ["RSA_DATABASE_PATH"] = str(_ROOT / "bootstrap.db")
os.environ["RSA_INSTANCE_DIR"] = str(_ROOT / "instance")
os.environ["RSA_UPLOAD_DIR"] = str(_ROOT / "uploads")
os.environ["RSA_SEED_DEMO_DATA"] = "0"
os.environ["RSA_ENV"] = "development"
os.environ.pop("RSA_ALLOW_UNLINKED_PROVIDERS", None)

PROJECT_DIR = Path(__file__).resolve().parent.parent
REAL_DB = PROJECT_DIR / "rsa.db"

_counter = [0]


def fresh_database(copy_from=None):
    """Point the application at a brand-new temp database (optionally a copy) and migrate it."""
    from database.models import create_tables
    from database.migrations import migrate

    _counter[0] += 1
    path = _ROOT / f"test-{_counter[0]}.db"
    if copy_from:
        # Read-only source connection + backup API: the source file is never written.
        source = sqlite3.connect(f"file:{copy_from}?mode=ro", uri=True)
        target = sqlite3.connect(path)
        source.backup(target)
        target.close()
        source.close()
    os.environ["RSA_DATABASE_PATH"] = str(path)
    create_tables()
    migrate(backup=False)
    return path


def make_user(name, email, role="driver", password="Password123!", phone=None, active=True):
    from authentication.auth import register_user
    from database.database import execute_query

    result = register_user(name, email, password, phone, role)
    assert result["success"], result
    if not active:
        execute_query("UPDATE users SET is_active = 0 WHERE id = ?", (result["user_id"],))
    return result["user_id"]


def make_provider(business_name, service_type, lat=20.2961, lon=85.8245, rating=4.5, linked=True,
                  verification="approved", availability="available", email=None):
    from database.database import execute_query

    user_id = None
    if linked:
        user_id = make_user(business_name, email or f"{business_name.lower().replace(' ', '.')}@example.test",
                            "provider")
    provider_id = execute_query(
        "INSERT INTO providers (user_id, business_name, service_type, phone, latitude, longitude, availability, "
        "rating, verification_status) VALUES (?, ?, ?, '9000000000', ?, ?, ?, ?, ?)",
        (user_id, business_name, service_type, lat, lon, availability, rating, verification),
    )
    return provider_id, user_id


def engines():
    from ai.diagnosis import DiagnosisEngine
    from ai.incident_analyzer import IncidentAnalyzer
    from ai.vehicle_health import VehicleHealthEngine
    from assistance.matching import AssistanceMatcher

    return dict(analyzer=IncidentAnalyzer(), matcher=AssistanceMatcher(), diagnosis_engine=DiagnosisEngine(),
                health_engine=VehicleHealthEngine())


def web_client(user_id=None, csrf="test-csrf-token"):
    """A Flask test client; optionally signed in as ``user_id`` with a known CSRF token."""
    import web

    client = web.app.test_client()
    with client.session_transaction() as session:
        session["_csrf"] = csrf
        if user_id:
            session["user_id"] = user_id
    client.csrf = csrf
    return client


def post(client, url, data=None, **kwargs):
    headers = kwargs.pop("headers", {})
    headers.setdefault("X-CSRF-Token", client.csrf)
    return client.post(url, data=data or {}, headers=headers, **kwargs)
