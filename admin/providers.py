"""
RSA Administrator - Provider Management
"""

import sqlite3
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "rsa.db"


def _connect():
    # Use the shared connection layer so RSA_DATABASE_PATH, foreign keys and
    # the busy timeout apply here too (previously a separate sqlite3.connect).
    from database.database import get_connection
    return get_connection()


def _find_provider_table(connection):
    cursor = connection.cursor()

    cursor.execute("""
        SELECT name
        FROM sqlite_master
        WHERE type = 'table'
        ORDER BY name
    """)

    tables = [row[0] for row in cursor.fetchall()]

    preferred = [
        "providers",
        "provider",
        "service_providers",
    ]

    for table in preferred:
        if table in tables:
            return table

    return None


def get_provider_count():
    try:
        connection = _connect()
        table = _find_provider_table(connection)

        if not table:
            connection.close()
            return 0

        cursor = connection.cursor()
        cursor.execute(f'SELECT COUNT(*) FROM "{table}"')

        count = cursor.fetchone()[0]

        connection.close()

        return count

    except Exception:
        return 0


def get_providers(limit=20):
    try:
        connection = _connect()
        table = _find_provider_table(connection)

        if not table:
            connection.close()
            return []

        cursor = connection.cursor()

        cursor.execute(f'PRAGMA table_info("{table}")')
        columns = [row[1] for row in cursor.fetchall()]

        cursor.execute(
            f'SELECT * FROM "{table}" LIMIT ?',
            (limit,)
        )

        rows = cursor.fetchall()

        connection.close()

        return {
            "table": table,
            "columns": columns,
            "rows": rows,
        }

    except Exception as error:
        return {
            "table": None,
            "columns": [],
            "rows": [],
            "error": str(error),
        }


def display_providers():
    print("\n" + "=" * 60)
    print("RSA ADMIN - SERVICE PROVIDERS")
    print("=" * 60)

    result = get_providers()

    if result.get("error"):
        print("Error:", result["error"])
        return

    if not result["table"]:
        print("No provider table found in database.")
        return

    print("Provider table :", result["table"])
    print("Provider count :", get_provider_count())

    if not result["rows"]:
        print("\nNo providers found.")
        return

    print("\nColumns:")
    print(" | ".join(result["columns"]))

    print("-" * 60)

    for row in result["rows"]:
        print(" | ".join(str(value) for value in row))

    print("=" * 60)


if __name__ == "__main__":
    display_providers()