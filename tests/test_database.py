"""Database integrity: atomic creation, rollback, foreign keys, migrations, record preservation."""
import hashlib
import os
import sqlite3
import unittest
from pathlib import Path
from unittest.mock import patch

from tests import support
from assistance import lifecycle
from database import migrations
from database.database import execute_query, fetch_all, fetch_one, transaction


def _md5(path):
    return hashlib.md5(Path(path).read_bytes()).hexdigest()


class TransactionTests(unittest.TestCase):

    def setUp(self):
        support.fresh_database()
        self.driver = support.make_user("Driver", "driver@example.test")

    def test_foreign_keys_enforced(self):
        with self.assertRaises(sqlite3.IntegrityError):
            execute_query("INSERT INTO service_matches (request_id, provider_id, status) VALUES (999, 999, 'ASSIGNED')")
        with self.assertRaises(sqlite3.IntegrityError):
            execute_query("INSERT INTO vehicles (user_id, registration_number) VALUES (424242, 'OD01AA0001')")

    def test_transaction_rolls_back_every_statement(self):
        before = fetch_one("SELECT COUNT(*) AS c FROM assistance_requests")["c"]
        with self.assertRaises(RuntimeError):
            with transaction() as conn:
                conn.execute("INSERT INTO assistance_requests (user_id, incident_type, priority, recommended_service) "
                             "VALUES (?, 'x', 'LOW', 'general_roadside_assistance')", (self.driver,))
                raise RuntimeError("simulated failure")
        self.assertEqual(fetch_one("SELECT COUNT(*) AS c FROM assistance_requests")["c"], before)

    def test_request_creation_is_atomic(self):
        """A failure while writing the request bundle leaves no partial request behind."""
        engines = support.engines()
        original = lifecycle._add_tracking

        def failing(*args, **kwargs):
            raise sqlite3.OperationalError("disk I/O error (simulated)")

        with patch.object(lifecycle, "_add_tracking", failing):
            with self.assertRaises(sqlite3.OperationalError):
                lifecycle.create_request(self.driver, "flat tyre on the highway", None, 20.29, 85.82, **engines)
        self.assertEqual(fetch_all("SELECT * FROM assistance_requests"), [])
        self.assertEqual(fetch_all("SELECT * FROM diagnosis_records"), [])
        self.assertIs(lifecycle._add_tracking, original)

    def test_assignment_failure_keeps_the_saved_request(self):
        support.make_provider("Mech", "Mechanic")
        engines = support.engines()
        with patch.object(lifecycle, "rank_providers", side_effect=sqlite3.OperationalError("locked")):
            result = lifecycle.create_request(self.driver, "engine stopped", None, 20.29, 85.82, **engines)
        self.assertFalse(result["assignment"]["assigned"])
        self.assertEqual(result["assignment"]["reason"], "assignment_error")
        self.assertEqual(fetch_one("SELECT status FROM assistance_requests WHERE id = ?",
                                   (result["request_id"],))["status"], "REQUESTED")
        # Later retry assigns it.
        self.assertEqual(lifecycle.retry_unassigned()["assigned"], 1)

    def test_missing_location_is_stored_as_null(self):
        result = lifecycle.create_request(self.driver, "battery is dead", None, "", "", **support.engines())
        row = fetch_one("SELECT latitude, longitude FROM assistance_requests WHERE id = ?", (result["request_id"],))
        self.assertIsNone(row["latitude"])
        self.assertIsNone(row["longitude"])

    def test_invalid_coordinates_rejected(self):
        from utils.validators import ValidationError
        for lat, lon in (("91", "10"), ("10", ""), ("abc", "1"), ("0", "0"), ("nan", "1")):
            with self.assertRaises(ValidationError, msg=(lat, lon)):
                lifecycle.create_request(self.driver, "battery is dead", None, lat, lon, **support.engines())

    def test_timestamps_are_utc_strings(self):
        result = lifecycle.create_request(self.driver, "flat tyre", None, 20.29, 85.82, **support.engines())
        created = fetch_one("SELECT created_at FROM assistance_requests WHERE id = ?", (result["request_id"],))
        self.assertRegex(created["created_at"], r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$")


class MigrationTests(unittest.TestCase):

    def test_real_database_copy_migrates_without_losing_records(self):
        if not support.REAL_DB.exists():
            self.skipTest("rsa.db not present")
        original_hash = _md5(support.REAL_DB)
        source = sqlite3.connect(f"file:{support.REAL_DB}?mode=ro", uri=True)
        tables = ["users", "providers", "vehicles", "assistance_requests", "service_matches", "tracking",
                  "diagnosis_records", "vehicle_health"]
        before = {}
        for table in tables:
            columns = [c[1] for c in source.execute(f"PRAGMA table_info({table})")]
            before[table] = (columns, source.execute(f"SELECT {','.join(columns)} FROM {table} ORDER BY id").fetchall())
        source.close()

        path = support.fresh_database(copy_from=support.REAL_DB)
        migrated = sqlite3.connect(path)
        for table, (columns, rows) in before.items():
            after = migrated.execute(f"SELECT {','.join(columns)} FROM {table} ORDER BY id").fetchall()
            self.assertEqual(after, rows, f"{table} records changed")
        self.assertEqual(migrated.execute("PRAGMA user_version").fetchone()[0], migrations.LATEST_VERSION)
        self.assertEqual(migrated.execute("PRAGMA integrity_check").fetchone()[0], "ok")
        self.assertEqual(migrated.execute("PRAGMA foreign_key_check").fetchall(), [])
        # Existing providers keep working after the new verification column is added.
        self.assertEqual({r[0] for r in migrated.execute("SELECT verification_status FROM providers")}, {"approved"})
        migrated.close()

        self.assertEqual(_md5(support.REAL_DB), original_hash, "the real rsa.db must never be modified by tests")

    def test_migration_is_idempotent_and_backs_up_first(self):
        path = support.fresh_database()
        support.make_user("Someone", "someone@example.test")
        conn = sqlite3.connect(path)
        conn.execute("PRAGMA user_version = 0")
        conn.commit()
        conn.close()
        report = migrations.migrate(path, backup=True)
        self.assertTrue(report["backup"])
        self.assertTrue(Path(report["backup"]).exists())
        backup = sqlite3.connect(report["backup"])
        self.assertEqual(backup.execute("SELECT COUNT(*) FROM users").fetchone()[0], 1)
        backup.close()
        again = migrations.migrate(path, backup=True)
        self.assertEqual(again["applied"], [])
        self.assertIsNone(again["backup"])

    def test_duplicate_active_matches_are_reported_not_deleted(self):
        path = support.fresh_database()
        conn = sqlite3.connect(path)
        conn.execute("DROP INDEX ux_service_matches_one_active_per_request")
        conn.execute("INSERT INTO users (name, email, password_hash) VALUES ('a', 'a@x.test', 'x')")
        conn.execute("INSERT INTO providers (business_name, service_type) VALUES ('p', 'Mechanic')")
        conn.execute("INSERT INTO assistance_requests (user_id, incident_type, priority, recommended_service) "
                     "VALUES (1, 'x', 'LOW', 'y')")
        conn.execute("INSERT INTO service_matches (request_id, provider_id, status) VALUES (1, 1, 'ASSIGNED')")
        conn.execute("INSERT INTO service_matches (request_id, provider_id, status) VALUES (1, 1, 'ON_THE_WAY')")
        conn.execute("PRAGMA user_version = 0")
        conn.commit()
        conn.close()
        report = migrations.migrate(path, backup=False)
        self.assertTrue(any("NOT created" in n for n in report["notes"]))
        conn = sqlite3.connect(path)
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM service_matches").fetchone()[0], 2)
        conn.close()


if __name__ == "__main__":
    unittest.main()


class BackupRestoreTests(unittest.TestCase):

    def test_backup_and_restore_round_trip(self):
        from database import backup
        path = support.fresh_database()
        uid = support.make_user("Keep Me", "keep@example.test")
        snapshot = migrations.backup_database(path, label="test")
        self.assertTrue(backup.verify(snapshot))

        execute_query("DELETE FROM users WHERE id = ?", (uid,))  # simulate data loss in the temp DB
        self.assertIsNone(fetch_one("SELECT id FROM users WHERE id = ?", (uid,)))

        result = backup.restore(snapshot, path)
        self.assertEqual(fetch_one("SELECT email FROM users WHERE id = ?", (uid,))["email"], "keep@example.test")
        self.assertTrue(Path(result["safety_copy"]).exists())
        self.assertEqual(result["schema_version"], migrations.LATEST_VERSION)

    def test_restore_rejects_a_corrupt_or_foreign_file(self):
        from database import backup
        path = support.fresh_database()
        junk = Path(path).with_name("junk.db")
        junk.write_bytes(b"this is not a database" * 100)
        with self.assertRaises(Exception):
            backup.restore(junk, path)
        other = Path(path).with_name("other.db")
        sqlite3.connect(other).execute("CREATE TABLE x (id INTEGER)").connection.close()
        with self.assertRaises(RuntimeError):
            backup.restore(other, path)
