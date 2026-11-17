"""
RSA database backup / restore
-----------------------------

    python -m database.backup create            # consistent online copy into backups/
    python -m database.backup list
    python -m database.backup verify <file>     # integrity check of a backup
    python -m database.backup restore <file>    # restores; current DB is backed up first

Restore safety:
- the backup is integrity-checked before anything is touched;
- the current database is itself backed up first (label "pre-restore");
- the restored database is migrated to the current schema afterwards.
Stop the web server before restoring.
"""

import sqlite3
import sys
from pathlib import Path

from .database import BUSY_TIMEOUT_SECONDS, get_database_path
from .migrations import backup_database, migrate


def verify(path):
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(path)
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        result = conn.execute("PRAGMA integrity_check").fetchone()[0]
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    finally:
        conn.close()
    if result != "ok":
        raise RuntimeError(f"Integrity check failed: {result}")
    missing = {"users", "assistance_requests"} - tables
    if missing:
        raise RuntimeError(f"Not an RSA database (missing tables: {', '.join(sorted(missing))})")
    return True


def list_backups(db_path=None):
    folder = Path(db_path or get_database_path()).parent / "backups"
    return sorted(folder.glob("*.db")) if folder.exists() else []


def restore(backup_file, db_path=None):
    db_path = Path(db_path or get_database_path())
    backup_file = Path(backup_file)
    verify(backup_file)

    safety_copy = backup_database(db_path, label="pre-restore") if db_path.exists() else None

    source = sqlite3.connect(f"file:{backup_file}?mode=ro", uri=True)
    target = sqlite3.connect(db_path, timeout=BUSY_TIMEOUT_SECONDS)
    try:
        source.backup(target)
    finally:
        target.close()
        source.close()

    verify(db_path)
    report = migrate(db_path, backup=False)
    return {"restored_from": str(backup_file), "safety_copy": str(safety_copy) if safety_copy else None,
            "schema_version": report["to_version"]}


def main(argv):
    command = argv[1] if len(argv) > 1 else "create"
    if command == "create":
        print(backup_database(label="manual"))
    elif command == "list":
        for item in list_backups():
            print(item)
    elif command == "verify" and len(argv) > 2:
        verify(argv[2])
        print("OK")
    elif command == "restore" and len(argv) > 2:
        answer = input(f"Restore {argv[2]} over {get_database_path()}? The current DB is backed up first. [y/N] ")
        if answer.strip().lower() == "y":
            print(restore(argv[2]))
        else:
            print("Cancelled.")
    else:
        print(__doc__)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
