"""
RSA Database Migrations
-----------------------

Versioned, additive, backward-compatible schema migrations.

Rules followed here:
- Never drop, recreate or rewrite an existing table; only ADD columns,
  CREATE new tables and CREATE indexes.
- Each migration runs inside one transaction and is recorded in both
  ``PRAGMA user_version`` and the ``schema_migrations`` table.
- Before any pending migration runs on a database that already holds data,
  a full copy is written to ``backups/`` next to the database using SQLite's
  online backup API.
- Every step is idempotent (columns/indexes are checked before creation), so a
  partially migrated database from an interrupted run is handled safely.

Run manually:   python -m database.migrations          (migrate)
                python -m database.migrations --status (show version only)
"""

import json
import logging
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

from .database import get_database_path, BUSY_TIMEOUT_SECONDS


logger = logging.getLogger("rsa.migrations")

ACTIVE_MATCH_STATUSES = ("ASSIGNED", "ACCEPTED", "ON_THE_WAY", "ARRIVED", "IN_PROGRESS")


# ==========================================================
# HELPERS
# ==========================================================

def _columns(conn, table):
    return {row[1] for row in conn.execute(f'PRAGMA table_info("{table}")')}


def _tables(conn):
    return {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}


def _indexes(conn):
    return {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='index'")}


def _add_column(conn, table, column, definition):
    if column not in _columns(conn, table):
        conn.execute(f'ALTER TABLE "{table}" ADD COLUMN {column} {definition}')
        return True
    return False


def _create_index(conn, name, sql, report):
    if name not in _indexes(conn):
        conn.execute(sql)
        report.append(f"created index {name}")


# ==========================================================
# MIGRATION 1 — indexes, lifecycle columns, integrity guards
# ==========================================================

def _migration_1(conn, report):
    # --- Lifecycle / audit columns (all nullable or defaulted, so old rows stay valid)
    if _add_column(conn, "service_matches", "updated_at", "TIMESTAMP"):
        conn.execute("UPDATE service_matches SET updated_at = created_at WHERE updated_at IS NULL")
        report.append("service_matches.updated_at added (back-filled from created_at)")
    if _add_column(conn, "service_matches", "status_reason", "TEXT"):
        report.append("service_matches.status_reason added")
    if _add_column(conn, "service_matches", "match_details", "TEXT"):
        report.append("service_matches.match_details added")

    if _add_column(conn, "tracking", "location_source", "TEXT"):
        report.append("tracking.location_source added (existing rows left NULL = unknown source)")

    if _add_column(conn, "assistance_requests", "ai_incident_type", "TEXT"):
        report.append("assistance_requests.ai_incident_type added")

    # Existing providers keep operating: they are marked approved. New self-registered
    # providers are inserted as 'pending' by the application.
    if _add_column(conn, "providers", "verification_status", "TEXT NOT NULL DEFAULT 'approved'"):
        report.append("providers.verification_status added (existing providers = approved)")
    if _add_column(conn, "providers", "location_updated_at", "TIMESTAMP"):
        report.append("providers.location_updated_at added")

    # --- Indexes for frequent queries
    index_sql = {
        "idx_assistance_requests_user_status":
            "CREATE INDEX idx_assistance_requests_user_status ON assistance_requests(user_id, status)",
        "idx_assistance_requests_status_priority":
            "CREATE INDEX idx_assistance_requests_status_priority ON assistance_requests(status, priority, created_at)",
        "idx_service_matches_request":
            "CREATE INDEX idx_service_matches_request ON service_matches(request_id)",
        "idx_service_matches_provider_status":
            "CREATE INDEX idx_service_matches_provider_status ON service_matches(provider_id, status)",
        "idx_tracking_request":
            "CREATE INDEX idx_tracking_request ON tracking(request_id, id)",
        "idx_diagnosis_records_request":
            "CREATE INDEX idx_diagnosis_records_request ON diagnosis_records(request_id)",
        "idx_vehicles_user":
            "CREATE INDEX idx_vehicles_user ON vehicles(user_id)",
        "idx_providers_user":
            "CREATE INDEX idx_providers_user ON providers(user_id)",
        "idx_vehicle_health_vehicle":
            "CREATE INDEX idx_vehicle_health_vehicle ON vehicle_health(vehicle_id, created_at)",
    }
    for name, sql in index_sql.items():
        _create_index(conn, name, sql, report)

    # --- At most ONE active assignment per request (prevents duplicate dispatch).
    duplicates = conn.execute(
        f"""
        SELECT request_id, COUNT(*) AS c FROM service_matches
        WHERE status IN ({",".join("?" * len(ACTIVE_MATCH_STATUSES))})
        GROUP BY request_id HAVING c > 1
        """,
        ACTIVE_MATCH_STATUSES,
    ).fetchall()
    if duplicates:
        # Do not delete or alter existing records; report so an admin can resolve them.
        report.append(
            "WARNING: unique active-assignment index NOT created; requests with several "
            f"active matches: {[row[0] for row in duplicates]}"
        )
    else:
        _create_index(
            conn,
            "ux_service_matches_one_active_per_request",
            "CREATE UNIQUE INDEX ux_service_matches_one_active_per_request ON service_matches(request_id) "
            f"WHERE status IN ({', '.join(repr(s) for s in ACTIVE_MATCH_STATUSES)})",
            report,
        )

    # --- One provider profile per user account
    dup_users = conn.execute(
        "SELECT user_id FROM providers WHERE user_id IS NOT NULL GROUP BY user_id HAVING COUNT(*) > 1"
    ).fetchall()
    if dup_users:
        report.append(
            "WARNING: unique provider-per-user index NOT created; users with several provider "
            f"profiles: {[row[0] for row in dup_users]}"
        )
    else:
        _create_index(
            conn,
            "ux_providers_user",
            "CREATE UNIQUE INDEX ux_providers_user ON providers(user_id) WHERE user_id IS NOT NULL",
            report,
        )


# ==========================================================
# MIGRATION 2 — notifications, audit log, login attempts,
#               feedback, attachments
# ==========================================================

def _migration_2(conn, report):
    tables = _tables(conn)

    if "notifications" not in tables:
        conn.execute(
            """
            CREATE TABLE notifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                request_id INTEGER,
                event_type TEXT NOT NULL,
                title TEXT NOT NULL,
                message TEXT NOT NULL,
                dedupe_key TEXT,
                is_read INTEGER NOT NULL DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY (request_id) REFERENCES assistance_requests(id) ON DELETE CASCADE
            )
            """
        )
        report.append("created table notifications")
    _create_index(conn, "idx_notifications_user_read",
                  "CREATE INDEX idx_notifications_user_read ON notifications(user_id, is_read, id)", report)
    _create_index(conn, "ux_notifications_dedupe",
                  "CREATE UNIQUE INDEX ux_notifications_dedupe ON notifications(user_id, dedupe_key) "
                  "WHERE dedupe_key IS NOT NULL", report)

    if "audit_log" not in tables:
        conn.execute(
            """
            CREATE TABLE audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                actor_user_id INTEGER,
                action TEXT NOT NULL,
                resource_type TEXT,
                resource_id INTEGER,
                metadata TEXT,
                ip_address TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (actor_user_id) REFERENCES users(id) ON DELETE SET NULL
            )
            """
        )
        report.append("created table audit_log")
    _create_index(conn, "idx_audit_log_created",
                  "CREATE INDEX idx_audit_log_created ON audit_log(created_at)", report)

    if "login_attempts" not in tables:
        conn.execute(
            """
            CREATE TABLE login_attempts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT,
                ip_address TEXT,
                success INTEGER NOT NULL DEFAULT 0,
                attempted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        report.append("created table login_attempts")
    _create_index(conn, "idx_login_attempts_email",
                  "CREATE INDEX idx_login_attempts_email ON login_attempts(email, attempted_at)", report)
    _create_index(conn, "idx_login_attempts_ip",
                  "CREATE INDEX idx_login_attempts_ip ON login_attempts(ip_address, attempted_at)", report)

    if "service_feedback" not in tables:
        conn.execute(
            """
            CREATE TABLE service_feedback (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                request_id INTEGER NOT NULL UNIQUE,
                user_id INTEGER NOT NULL,
                provider_id INTEGER,
                rating INTEGER NOT NULL CHECK (rating BETWEEN 1 AND 5),
                comment TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (request_id) REFERENCES assistance_requests(id) ON DELETE CASCADE,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY (provider_id) REFERENCES providers(id) ON DELETE SET NULL
            )
            """
        )
        report.append("created table service_feedback")
    _create_index(conn, "idx_service_feedback_provider",
                  "CREATE INDEX idx_service_feedback_provider ON service_feedback(provider_id)", report)

    if "request_attachments" not in tables:
        conn.execute(
            """
            CREATE TABLE request_attachments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                request_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                original_name TEXT,
                stored_name TEXT NOT NULL UNIQUE,
                content_type TEXT NOT NULL,
                size_bytes INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (request_id) REFERENCES assistance_requests(id) ON DELETE CASCADE,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
            """
        )
        report.append("created table request_attachments")
    _create_index(conn, "idx_request_attachments_request",
                  "CREATE INDEX idx_request_attachments_request ON request_attachments(request_id)", report)


MIGRATIONS = [
    (1, "indexes_lifecycle_columns_integrity", _migration_1),
    (2, "notifications_audit_login_feedback_attachments", _migration_2),
]

LATEST_VERSION = MIGRATIONS[-1][0]


# ==========================================================
# BACKUP
# ==========================================================

def backup_database(db_path=None, label="manual"):
    """Copy the database with SQLite's online backup API. Returns the backup path."""

    db_path = Path(db_path or get_database_path())
    backup_dir = db_path.parent / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    target = backup_dir / f"{db_path.stem}-{stamp}-{label}.db"

    source = sqlite3.connect(db_path, timeout=BUSY_TIMEOUT_SECONDS)
    try:
        destination = sqlite3.connect(target)
        try:
            source.backup(destination)
        finally:
            destination.close()
    finally:
        source.close()

    # Verify the copy is a readable, intact database before relying on it.
    check = sqlite3.connect(f"file:{target}?mode=ro", uri=True)
    try:
        result = check.execute("PRAGMA integrity_check").fetchone()[0]
    finally:
        check.close()
    if result != "ok":
        raise RuntimeError(f"Backup integrity check failed for {target}: {result}")

    return target


# ==========================================================
# MIGRATE
# ==========================================================

def get_schema_version(db_path=None):
    conn = sqlite3.connect(Path(db_path or get_database_path()), timeout=BUSY_TIMEOUT_SECONDS)
    try:
        return conn.execute("PRAGMA user_version").fetchone()[0]
    finally:
        conn.close()


def migrate(db_path=None, backup=True):
    """
    Apply pending migrations. Returns a dict report.

    Safe to call on every application start: if the schema is current it does
    nothing (and makes no backup).
    """

    db_path = Path(db_path or get_database_path())
    conn = sqlite3.connect(db_path, timeout=BUSY_TIMEOUT_SECONDS, isolation_level=None)
    conn.execute("PRAGMA foreign_keys = ON")

    result = {"database": str(db_path), "from_version": None, "to_version": None,
              "applied": [], "backup": None, "notes": []}

    try:
        current = conn.execute("PRAGMA user_version").fetchone()[0]
        result["from_version"] = current
        pending = [m for m in MIGRATIONS if m[0] > current]

        if not pending:
            result["to_version"] = current
            return result

        has_data = bool(conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='users'"
        ).fetchone()) and bool(conn.execute("SELECT 1 FROM users LIMIT 1").fetchone())

        if backup and has_data:
            result["backup"] = str(backup_database(db_path, label=f"pre-v{pending[-1][0]}"))

        for version, name, function in pending:
            report = []
            conn.execute("BEGIN IMMEDIATE")
            try:
                if "schema_migrations" not in _tables(conn):
                    conn.execute(
                        "CREATE TABLE schema_migrations (version INTEGER PRIMARY KEY, "
                        "name TEXT NOT NULL, applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, details TEXT)"
                    )
                function(conn, report)
                conn.execute(
                    "INSERT OR REPLACE INTO schema_migrations(version, name, details) VALUES (?, ?, ?)",
                    (version, name, json.dumps(report)),
                )
                conn.execute(f"PRAGMA user_version = {int(version)}")
                conn.execute("COMMIT")
            except Exception:
                conn.execute("ROLLBACK")
                raise
            result["applied"].append({"version": version, "name": name, "changes": report})
            for line in report:
                if line.startswith("WARNING"):
                    result["notes"].append(line)
                    logger.warning(line)

        # Report (never "fix") pre-existing foreign-key violations.
        violations = conn.execute("PRAGMA foreign_key_check").fetchall()
        if violations:
            result["notes"].append(f"WARNING: {len(violations)} foreign-key violations exist: {violations[:10]}")

        result["to_version"] = conn.execute("PRAGMA user_version").fetchone()[0]
        return result

    finally:
        conn.close()


if __name__ == "__main__":
    if "--status" in sys.argv:
        print(f"Database: {get_database_path()}  schema version: {get_schema_version()} "
              f"(latest {LATEST_VERSION})")
    else:
        from .models import create_tables
        create_tables()
        print(json.dumps(migrate(), indent=2))
