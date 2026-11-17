"""
RSA Database Connection Layer

Provides SQLite database connectivity for the
Roadside Assistance (RSA) application.

Backward compatible with the original module:
``DATABASE_PATH``, ``get_connection``, ``execute_query``, ``fetch_one``,
``fetch_all`` and ``initialize_database`` keep their names and behaviour.

Additions:
- The database location can be overridden with the ``RSA_DATABASE_PATH``
  environment variable (used by tests so they never touch the real rsa.db).
- ``transaction()`` gives an atomic unit of work (BEGIN IMMEDIATE ... COMMIT,
  ROLLBACK on any exception) for multi-statement operations such as request
  creation and provider assignment.
- Every connection enables foreign keys and a busy timeout.
- Timestamps are stored as UTC ``YYYY-MM-DD HH:MM:SS`` strings, the same format
  SQLite's ``CURRENT_TIMESTAMP`` already produces for the existing records.
"""

import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path


# Project root directory
BASE_DIR = Path(__file__).resolve().parent.parent

# Default SQLite database file (unchanged location: <project>/rsa.db)
DATABASE_PATH = BASE_DIR / "rsa.db"

# Seconds SQLite waits for a lock held by another connection before failing.
BUSY_TIMEOUT_SECONDS = 10


def get_database_path() -> Path:
    """Return the active database path (``RSA_DATABASE_PATH`` overrides the default)."""

    override = os.environ.get("RSA_DATABASE_PATH", "").strip()

    if override:
        return Path(override).expanduser().resolve()

    return DATABASE_PATH


def utc_now() -> str:
    """Current UTC time in the same format SQLite's CURRENT_TIMESTAMP uses."""

    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def _configure(connection: sqlite3.Connection) -> sqlite3.Connection:
    # Return database rows as dictionary-like objects
    connection.row_factory = sqlite3.Row

    # Enable foreign-key support (SQLite disables it per connection by default)
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute(f"PRAGMA busy_timeout = {BUSY_TIMEOUT_SECONDS * 1000}")

    return connection


def get_connection():
    """
    Create and return a SQLite database connection.
    """

    connection = sqlite3.connect(
        get_database_path(),
        check_same_thread=False,
        timeout=BUSY_TIMEOUT_SECONDS,
    )

    return _configure(connection)


@contextmanager
def transaction():
    """
    Atomic unit of work.

    Usage::

        with transaction() as conn:
            conn.execute("INSERT ...")
            conn.execute("UPDATE ...")

    ``BEGIN IMMEDIATE`` takes the write lock up front, so two concurrent
    status updates cannot both read the same "current" state and both win.
    Any exception rolls back every statement in the block and is re-raised.
    """

    connection = sqlite3.connect(
        get_database_path(),
        check_same_thread=False,
        timeout=BUSY_TIMEOUT_SECONDS,
        isolation_level=None,  # we issue BEGIN/COMMIT ourselves
    )
    _configure(connection)

    try:
        connection.execute("BEGIN IMMEDIATE")
        yield connection
        connection.execute("COMMIT")
    except BaseException:
        try:
            connection.execute("ROLLBACK")
        except sqlite3.Error:
            pass
        raise
    finally:
        connection.close()


def execute_query(query, parameters=()):
    """
    Execute INSERT, UPDATE or DELETE queries.
    Returns the last inserted row ID.
    """

    connection = get_connection()

    try:
        cursor = connection.cursor()

        cursor.execute(query, parameters)

        connection.commit()

        return cursor.lastrowid

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


def fetch_one(query, parameters=()):
    """
    Execute a SELECT query and return one row.
    """

    connection = get_connection()

    try:
        cursor = connection.cursor()

        cursor.execute(query, parameters)

        return cursor.fetchone()

    finally:
        connection.close()


def fetch_all(query, parameters=()):
    """
    Execute a SELECT query and return all rows.
    """

    connection = get_connection()

    try:
        cursor = connection.cursor()

        cursor.execute(query, parameters)

        return cursor.fetchall()

    finally:
        connection.close()


def initialize_database():
    """
    Initialize the RSA database.

    Table creation will be handled by models.py.
    """

    connection = get_connection()

    try:
        connection.commit()

    finally:
        connection.close()


if __name__ == "__main__":
    initialize_database()

    print("=" * 60)
    print("RSA DATABASE CONNECTION TEST")
    print("=" * 60)
    print(f"Database path : {get_database_path()}")
    print("Status        : DATABASE CONNECTION SUCCESSFUL")
    print("=" * 60)
