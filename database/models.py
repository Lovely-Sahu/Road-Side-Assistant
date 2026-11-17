"""
RSA Database Models

Creates all core database tables required by the
Roadside Assistance application.
"""

from .database import get_connection


def create_tables():
    """Create all RSA database tables."""

    connection = get_connection()
    cursor = connection.cursor()

    # ==========================================================
    # USERS
    # ==========================================================

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            phone TEXT UNIQUE,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'driver',
            is_active INTEGER NOT NULL DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # ==========================================================
    # VEHICLES
    # ==========================================================

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS vehicles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            registration_number TEXT NOT NULL UNIQUE,
            make TEXT,
            model TEXT,
            year INTEGER,
            fuel_type TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

            FOREIGN KEY (user_id)
                REFERENCES users(id)
                ON DELETE CASCADE
        )
    """)

    # ==========================================================
    # PROVIDERS
    # ==========================================================

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS providers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            business_name TEXT NOT NULL,
            service_type TEXT NOT NULL,
            phone TEXT,
            latitude REAL,
            longitude REAL,
            availability TEXT DEFAULT 'available',
            rating REAL DEFAULT 0.0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

            FOREIGN KEY (user_id)
                REFERENCES users(id)
                ON DELETE SET NULL
        )
    """)

    # ==========================================================
    # ASSISTANCE REQUESTS
    # ==========================================================

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS assistance_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            vehicle_id INTEGER,
            incident_type TEXT NOT NULL,
            description TEXT,
            priority TEXT NOT NULL,
            recommended_service TEXT NOT NULL,
            escalation INTEGER NOT NULL DEFAULT 0,
            safe_to_drive INTEGER NOT NULL DEFAULT 1,
            status TEXT NOT NULL DEFAULT 'REQUESTED',
            latitude REAL,
            longitude REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

            FOREIGN KEY (user_id)
                REFERENCES users(id)
                ON DELETE CASCADE,

            FOREIGN KEY (vehicle_id)
                REFERENCES vehicles(id)
                ON DELETE SET NULL
        )
    """)

    # ==========================================================
    # SERVICE MATCHES
    # ==========================================================

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS service_matches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            request_id INTEGER NOT NULL,
            provider_id INTEGER NOT NULL,
            match_score REAL DEFAULT 0.0,
            distance_km REAL,
            status TEXT NOT NULL DEFAULT 'MATCHED',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

            FOREIGN KEY (request_id)
                REFERENCES assistance_requests(id)
                ON DELETE CASCADE,

            FOREIGN KEY (provider_id)
                REFERENCES providers(id)
                ON DELETE CASCADE
        )
    """)

    # ==========================================================
    # TRACKING
    # ==========================================================

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tracking (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            request_id INTEGER NOT NULL,
            provider_id INTEGER,
            status TEXT NOT NULL,
            latitude REAL,
            longitude REAL,
            estimated_arrival_minutes INTEGER,
            notes TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

            FOREIGN KEY (request_id)
                REFERENCES assistance_requests(id)
                ON DELETE CASCADE,

            FOREIGN KEY (provider_id)
                REFERENCES providers(id)
                ON DELETE SET NULL
        )
    """)

    # ==========================================================
    # DIAGNOSIS RECORDS
    # ==========================================================

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS diagnosis_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            request_id INTEGER NOT NULL,
            diagnosis TEXT,
            severity TEXT,
            confidence REAL,
            explanation TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

            FOREIGN KEY (request_id)
                REFERENCES assistance_requests(id)
                ON DELETE CASCADE
        )
    """)

    # ==========================================================
    # VEHICLE HEALTH
    # ==========================================================

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS vehicle_health (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            vehicle_id INTEGER NOT NULL,
            health_score REAL,
            engine_status TEXT,
            brake_status TEXT,
            tyre_status TEXT,
            battery_status TEXT,
            electrical_status TEXT,
            overall_status TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

            FOREIGN KEY (vehicle_id)
                REFERENCES vehicles(id)
                ON DELETE CASCADE
        )
    """)

    connection.commit()
    connection.close()


if __name__ == "__main__":

    create_tables()

    print("=" * 60)
    print("RSA DATABASE MODEL TEST")
    print("=" * 60)
    print("Status : ALL TABLES CREATED SUCCESSFULLY")
    print("=" * 60)