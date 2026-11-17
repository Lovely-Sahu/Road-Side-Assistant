"""
RSA Administrator - Analytics
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


def get_database_tables():
    try:
        connection = _connect()
        cursor = connection.cursor()

        cursor.execute("""
            SELECT name
            FROM sqlite_master
            WHERE type = 'table'
            ORDER BY name
        """)

        tables = [row[0] for row in cursor.fetchall()]

        connection.close()

        return tables

    except Exception:
        return []


def get_table_counts():
    results = {}

    try:
        connection = _connect()
        cursor = connection.cursor()

        for table in get_database_tables():
            try:
                cursor.execute(f'SELECT COUNT(*) FROM "{table}"')
                results[table] = cursor.fetchone()[0]
            except Exception:
                results[table] = 0

        connection.close()

    except Exception:
        pass

    return results


def display_analytics():
    print("\n" + "=" * 60)
    print("RSA ADMIN - SYSTEM ANALYTICS")
    print("=" * 60)

    tables = get_database_tables()

    if not tables:
        print("No database tables found.")
        return

    counts = get_table_counts()

    print("\nDATABASE TABLES")
    print("-" * 60)

    for table in tables:
        print(f"{table:<35} : {counts.get(table, 0)} records")

    print("=" * 60)


if __name__ == "__main__":
    display_analytics()