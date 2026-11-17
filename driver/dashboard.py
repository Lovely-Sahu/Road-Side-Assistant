"""
RSA Driver Dashboard
--------------------

Provides dashboard information for authenticated drivers.

Includes:
- Driver information
- Vehicle summary
- Assistance request summary
- Active request
- Recent request history
- Complete dashboard
- Lightweight dashboard status
- Interactive dashboard
- Module tests
"""

from database.database import fetch_one, fetch_all, execute_query


# ==========================================================
# DRIVER INFORMATION
# ==========================================================

def get_driver_info(user_id: int):
    """
    Return basic information about a driver.
    """

    if not user_id:
        return None

    user = fetch_one(
        """
        SELECT
            id,
            name,
            email,
            phone,
            role,
            is_active,
            created_at
        FROM users
        WHERE id = ?
        """,
        (user_id,),
    )

    if not user:
        return None

    return dict(user)


# ==========================================================
# VEHICLE SUMMARY
# ==========================================================

def get_vehicle_summary(user_id: int):
    """
    Return vehicle information belonging to the driver.
    """

    vehicles = fetch_all(
        """
        SELECT
            id,
            registration_number,
            make,
            model,
            year,
            fuel_type,
            created_at
        FROM vehicles
        WHERE user_id = ?
        ORDER BY created_at DESC
        """,
        (user_id,),
    )

    vehicles = [dict(vehicle) for vehicle in vehicles]

    return {
        "vehicle_count": len(vehicles),
        "vehicles": vehicles,
    }


# ==========================================================
# REQUEST SUMMARY
# ==========================================================

def get_request_summary(user_id: int):
    """
    Return assistance request statistics for a driver.
    """

    total = fetch_one(
        """
        SELECT COUNT(*) AS count
        FROM assistance_requests
        WHERE user_id = ?
        """,
        (user_id,),
    )

    active = fetch_one(
        """
        SELECT COUNT(*) AS count
        FROM assistance_requests
        WHERE user_id = ?
        AND status NOT IN (
            'COMPLETED',
            'CANCELLED'
        )
        """,
        (user_id,),
    )

    completed = fetch_one(
        """
        SELECT COUNT(*) AS count
        FROM assistance_requests
        WHERE user_id = ?
        AND status = 'COMPLETED'
        """,
        (user_id,),
    )

    return {
        "total_requests": total["count"] if total else 0,
        "active_requests": active["count"] if active else 0,
        "completed_requests": completed["count"] if completed else 0,
    }


# ==========================================================
# ACTIVE REQUEST
# ==========================================================

def get_active_request(user_id: int):
    """
    Return the driver's most recent active assistance request.
    """

    request = fetch_one(
        """
        SELECT
            id,
            vehicle_id,
            incident_type,
            description,
            priority,
            recommended_service,
            escalation,
            safe_to_drive,
            status,
            latitude,
            longitude,
            created_at,
            updated_at
        FROM assistance_requests
        WHERE user_id = ?
        AND status NOT IN (
            'COMPLETED',
            'CANCELLED'
        )
        ORDER BY created_at DESC
        LIMIT 1
        """,
        (user_id,),
    )

    if not request:
        return None

    return dict(request)


# ==========================================================
# RECENT REQUESTS
# ==========================================================

def get_recent_requests(
    user_id: int,
    limit: int = 5,
):
    """
    Return recent assistance requests.
    """

    if not isinstance(limit, int) or limit <= 0:
        limit = 5

    requests = fetch_all(
        """
        SELECT
            id,
            vehicle_id,
            incident_type,
            priority,
            recommended_service,
            escalation,
            safe_to_drive,
            status,
            created_at,
            updated_at
        FROM assistance_requests
        WHERE user_id = ?
        ORDER BY created_at DESC
        LIMIT ?
        """,
        (
            user_id,
            limit,
        ),
    )

    return [dict(request) for request in requests]


# ==========================================================
# COMPLETE DASHBOARD
# ==========================================================

def get_dashboard(user_id: int):
    """
    Build the complete driver dashboard.
    """

    driver = get_driver_info(user_id)

    if not driver:
        return {
            "success": False,
            "message": "Driver not found.",
        }

    # Make sure the logged-in account is a driver.
    if driver["role"] != "driver":
        return {
            "success": False,
            "message": "This account is not a driver account.",
        }

    # Make sure the driver account is active.
    if not bool(driver["is_active"]):
        return {
            "success": False,
            "message": "Driver account is inactive.",
        }

    vehicles = get_vehicle_summary(user_id)
    requests = get_request_summary(user_id)
    active_request = get_active_request(user_id)
    recent_requests = get_recent_requests(user_id)

    return {
        "success": True,
        "message": "Driver dashboard loaded successfully.",
        "driver": driver,
        "vehicles": vehicles,
        "requests": requests,
        "active_request": active_request,
        "recent_requests": recent_requests,
    }


# ==========================================================
# DASHBOARD STATUS
# ==========================================================

def get_dashboard_status(user_id: int):
    """
    Return a lightweight dashboard status.
    """

    driver = get_driver_info(user_id)

    if not driver:
        return {
            "success": False,
            "message": "Driver not found.",
        }

    if driver["role"] != "driver":
        return {
            "success": False,
            "message": "This account is not a driver account.",
        }

    if not bool(driver["is_active"]):
        return {
            "success": False,
            "message": "Driver account is inactive.",
        }

    request_summary = get_request_summary(user_id)
    vehicle_summary = get_vehicle_summary(user_id)

    return {
        "success": True,
        "driver_name": driver["name"],
        "vehicle_count": vehicle_summary["vehicle_count"],
        "total_requests": request_summary["total_requests"],
        "active_requests": request_summary["active_requests"],
        "completed_requests": request_summary["completed_requests"],
    }


# ==========================================================
# DISPLAY DRIVER INFORMATION
# ==========================================================

def display_driver_info(driver):
    """
    Display driver information.
    """

    print("\n" + "=" * 60)
    print("DRIVER INFORMATION")
    print("=" * 60)

    print(f"ID        : {driver['id']}")
    print(f"Name      : {driver['name']}")
    print(f"Email     : {driver['email']}")
    print(f"Phone     : {driver['phone'] or 'Not provided'}")
    print(f"Role      : {driver['role']}")
    print(
        f"Status    : "
        f"{'ACTIVE' if driver['is_active'] else 'INACTIVE'}"
    )
    print(f"Created   : {driver['created_at']}")


# ==========================================================
# DISPLAY VEHICLES
# ==========================================================

def display_vehicles(vehicle_summary):
    """
    Display driver's vehicles.
    """

    print("\n" + "=" * 60)
    print("MY VEHICLES")
    print("=" * 60)

    print(
        f"Total vehicles : "
        f"{vehicle_summary['vehicle_count']}"
    )

    if not vehicle_summary["vehicles"]:
        print("\nNo vehicles registered.")
        return

    for index, vehicle in enumerate(
        vehicle_summary["vehicles"],
        start=1,
    ):
        print(f"\nVehicle #{index}")
        print("-" * 40)

        print(f"ID           : {vehicle['id']}")
        print(
            f"Registration : "
            f"{vehicle['registration_number']}"
        )
        print(f"Make         : {vehicle['make']}")
        print(f"Model        : {vehicle['model']}")
        print(f"Year         : {vehicle['year']}")
        print(f"Fuel Type    : {vehicle['fuel_type']}")
        print(f"Added        : {vehicle['created_at']}")


# ==========================================================
# DISPLAY REQUEST SUMMARY
# ==========================================================

def display_request_summary(requests):
    """
    Display assistance request statistics.
    """

    print("\n" + "=" * 60)
    print("ASSISTANCE REQUEST SUMMARY")
    print("=" * 60)

    print(
        f"Total Requests     : "
        f"{requests['total_requests']}"
    )

    print(
        f"Active Requests    : "
        f"{requests['active_requests']}"
    )

    print(
        f"Completed Requests : "
        f"{requests['completed_requests']}"
    )


# ==========================================================
# DISPLAY ACTIVE REQUEST
# ==========================================================

def display_active_request(request):
    """
    Display the driver's active request.
    """

    print("\n" + "=" * 60)
    print("ACTIVE ASSISTANCE REQUEST")
    print("=" * 60)

    if not request:
        print("No active assistance request.")
        return

    print(f"Request ID          : {request['id']}")
    print(f"Vehicle ID          : {request['vehicle_id']}")
    print(f"Incident Type       : {request['incident_type']}")
    print(f"Description         : {request['description']}")
    print(f"Priority            : {request['priority']}")
    print(
        f"Recommended Service : "
        f"{request['recommended_service']}"
    )
    print(f"Escalation          : {request['escalation']}")
    print(
        f"Safe To Drive       : "
        f"{'YES' if request['safe_to_drive'] else 'NO'}"
    )
    print(f"Status              : {request['status']}")
    print(f"Created             : {request['created_at']}")
    print(f"Updated             : {request['updated_at']}")

    if request["latitude"] is not None:
        print(
            f"Latitude            : "
            f"{request['latitude']}"
        )

    if request["longitude"] is not None:
        print(
            f"Longitude           : "
            f"{request['longitude']}"
        )


# ==========================================================
# DISPLAY RECENT REQUESTS
# ==========================================================

def display_recent_requests(requests):
    """
    Display recent assistance requests.
    """

    print("\n" + "=" * 60)
    print("RECENT ASSISTANCE REQUESTS")
    print("=" * 60)

    if not requests:
        print("No request history.")
        return

    for index, request in enumerate(
        requests,
        start=1,
    ):
        print(f"\nRequest #{index}")
        print("-" * 40)

        print(f"Request ID          : {request['id']}")
        print(f"Vehicle ID          : {request['vehicle_id']}")
        print(
            f"Incident Type       : "
            f"{request['incident_type']}"
        )
        print(f"Priority            : {request['priority']}")
        print(
            f"Recommended Service : "
            f"{request['recommended_service']}"
        )
        print(f"Escalation          : {request['escalation']}")
        print(
            f"Safe To Drive       : "
            f"{'YES' if request['safe_to_drive'] else 'NO'}"
        )
        print(f"Status              : {request['status']}")
        print(f"Created             : {request['created_at']}")
        print(f"Updated             : {request['updated_at']}")


# ==========================================================
# INTERACTIVE DRIVER DASHBOARD
# ==========================================================

def main(user_id=None):
    """
    Run the interactive driver dashboard.

    When app.py already knows the logged-in user's ID,
    call:

        main(user_id)

    If no user_id is supplied, this function asks for one.
    """

    print("\n" + "=" * 60)
    print("RSA DRIVER DASHBOARD")
    print("=" * 60)

    # ------------------------------------------------------
    # Get user ID for standalone testing
    # ------------------------------------------------------

    if user_id is None:

        try:
            user_id = int(
                input("Enter Driver User ID: ").strip()
            )

        except ValueError:
            print("\nInvalid user ID.")
            return

    # ------------------------------------------------------
    # Load dashboard
    # ------------------------------------------------------

    dashboard = get_dashboard(user_id)

    if not dashboard["success"]:
        print(
            f"\nError: {dashboard['message']}"
        )
        return

    # ------------------------------------------------------
    # Dashboard loop
    # ------------------------------------------------------

    while True:

        driver = dashboard["driver"]

        print("\n" + "=" * 60)
        print(
            f"Welcome, {driver['name']}!"
        )
        print("=" * 60)

        print("1. View Driver Information")
        print("2. View My Vehicles")
        print("3. View Request Summary")
        print("4. View Active Request")
        print("5. View Recent Requests")
        print("6. Refresh Dashboard")
        print("0. Logout / Return")

        print("=" * 60)

        choice = input(
            "Enter your choice: "
        ).strip()

        # --------------------------------------------------
        # Driver information
        # --------------------------------------------------

        if choice == "1":

            display_driver_info(
                dashboard["driver"]
            )

        # --------------------------------------------------
        # Vehicles
        # --------------------------------------------------

        elif choice == "2":

            display_vehicles(
                dashboard["vehicles"]
            )

        # --------------------------------------------------
        # Request summary
        # --------------------------------------------------

        elif choice == "3":

            display_request_summary(
                dashboard["requests"]
            )

        # --------------------------------------------------
        # Active request
        # --------------------------------------------------

        elif choice == "4":

            display_active_request(
                dashboard["active_request"]
            )

        # --------------------------------------------------
        # Recent requests
        # --------------------------------------------------

        elif choice == "5":

            display_recent_requests(
                dashboard["recent_requests"]
            )

        # --------------------------------------------------
        # Refresh dashboard
        # --------------------------------------------------

        elif choice == "6":

            dashboard = get_dashboard(user_id)

            if not dashboard["success"]:

                print(
                    f"\nError: {dashboard['message']}"
                )

                return

            print(
                "\nDashboard refreshed successfully."
            )

        # --------------------------------------------------
        # Logout
        # --------------------------------------------------

        elif choice == "0":

            print(
                "\nReturning to RSA Main Menu..."
            )

            break

        # --------------------------------------------------
        # Invalid option
        # --------------------------------------------------

        else:

            print(
                "\nInvalid choice."
            )

            print(
                "Please enter 0, 1, 2, 3, 4, 5, or 6."
            )


# ==========================================================
# DASHBOARD MODULE TESTS
# ==========================================================

def run_tests():
    """
    Run dashboard module tests.

    Test records use unique email, phone and vehicle
    registration values so they do not conflict with
    existing database records.
    """

    print("=" * 60)
    print("RSA DRIVER DASHBOARD TEST")
    print("=" * 60)

    # ------------------------------------------------------
    # Unique test values
    # ------------------------------------------------------

    test_email = "dashboard_test_2026@rsa.com"
    test_phone = "9999999901"
    test_registration = "TS09DASH01"

    # ------------------------------------------------------
    # Cleanup old test data
    #
    # Delete requests and vehicles first because they may
    # reference the test user.
    # ------------------------------------------------------

    old_user = fetch_one(
        """
        SELECT id
        FROM users
        WHERE email = ?
           OR phone = ?
        LIMIT 1
        """,
        (
            test_email,
            test_phone,
        ),
    )

    if old_user:

        old_user_id = old_user["id"]

        execute_query(
            """
            DELETE FROM assistance_requests
            WHERE user_id = ?
            """,
            (old_user_id,),
        )

        execute_query(
            """
            DELETE FROM vehicles
            WHERE user_id = ?
            """,
            (old_user_id,),
        )

        execute_query(
            """
            DELETE FROM users
            WHERE id = ?
            """,
            (old_user_id,),
        )

    # Also remove an old test vehicle if it somehow remains.
    execute_query(
        """
        DELETE FROM vehicles
        WHERE registration_number = ?
        """,
        (test_registration,),
    )

    # ------------------------------------------------------
    # Create test driver
    # ------------------------------------------------------

    user_id = execute_query(
        """
        INSERT INTO users (
            name,
            email,
            phone,
            password_hash,
            role,
            is_active
        )
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            "Dashboard Test Driver",
            test_email,
            test_phone,
            "test_hash",
            "driver",
            1,
        ),
    )

    print(
        "Test driver created:",
        "PASS" if user_id else "FAIL",
    )

    # ------------------------------------------------------
    # Driver information
    # ------------------------------------------------------

    driver = get_driver_info(user_id)

    print(
        "Driver info       :",
        "PASS"
        if driver
        and driver["id"] == user_id
        and driver["role"] == "driver"
        else "FAIL",
    )

    # ------------------------------------------------------
    # Create test vehicle
    # ------------------------------------------------------

    vehicle_id = execute_query(
        """
        INSERT INTO vehicles (
            user_id,
            registration_number,
            make,
            model,
            year,
            fuel_type
        )
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            user_id,
            test_registration,
            "Toyota",
            "Innova",
            2023,
            "Diesel",
        ),
    )

    print(
        "Test vehicle      :",
        "PASS" if vehicle_id else "FAIL",
    )

    # ------------------------------------------------------
    # Vehicle summary
    # ------------------------------------------------------

    vehicles = get_vehicle_summary(user_id)

    print(
        "Vehicle summary   :",
        "PASS"
        if vehicles["vehicle_count"] == 1
        and vehicles["vehicles"][0]["id"] == vehicle_id
        else "FAIL",
    )

    # ------------------------------------------------------
    # Create test request
    # ------------------------------------------------------

    request_id = execute_query(
        """
        INSERT INTO assistance_requests (
            user_id,
            vehicle_id,
            incident_type,
            description,
            priority,
            recommended_service,
            escalation,
            safe_to_drive,
            status
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            user_id,
            vehicle_id,
            "BREAKDOWN",
            "Engine stopped suddenly.",
            "HIGH",
            "Tow Service",
            1,
            0,
            "REQUESTED",
        ),
    )

    print(
        "Test request      :",
        "PASS" if request_id else "FAIL",
    )

    # ------------------------------------------------------
    # Request summary
    # ------------------------------------------------------

    summary = get_request_summary(user_id)

    print(
        "Request summary   :",
        "PASS"
        if summary["total_requests"] == 1
        and summary["active_requests"] == 1
        and summary["completed_requests"] == 0
        else "FAIL",
    )

    # ------------------------------------------------------
    # Active request
    # ------------------------------------------------------

    active = get_active_request(user_id)

    print(
        "Active request    :",
        "PASS"
        if active
        and active["id"] == request_id
        and active["status"] == "REQUESTED"
        else "FAIL",
    )

    # ------------------------------------------------------
    # Recent requests
    # ------------------------------------------------------

    recent = get_recent_requests(user_id)

    print(
        "Recent requests   :",
        "PASS"
        if len(recent) == 1
        and recent[0]["id"] == request_id
        else "FAIL",
    )

    # ------------------------------------------------------
    # Complete dashboard
    # ------------------------------------------------------

    dashboard = get_dashboard(user_id)

    print(
        "Dashboard         :",
        "PASS"
        if dashboard["success"]
        and dashboard["driver"]["id"] == user_id
        and dashboard["vehicles"]["vehicle_count"] == 1
        and dashboard["requests"]["total_requests"] == 1
        and dashboard["active_request"]["id"] == request_id
        else "FAIL",
    )

    # ------------------------------------------------------
    # Dashboard status
    # ------------------------------------------------------

    status = get_dashboard_status(user_id)

    print(
        "Dashboard status  :",
        "PASS"
        if status["success"]
        and status["driver_name"] == "Dashboard Test Driver"
        and status["vehicle_count"] == 1
        and status["total_requests"] == 1
        and status["active_requests"] == 1
        and status["completed_requests"] == 0
        else "FAIL",
    )

    # ------------------------------------------------------
    # Cleanup test request
    # ------------------------------------------------------

    execute_query(
        """
        DELETE FROM assistance_requests
        WHERE user_id = ?
        """,
        (user_id,),
    )

    # ------------------------------------------------------
    # Cleanup test vehicle
    # ------------------------------------------------------

    execute_query(
        """
        DELETE FROM vehicles
        WHERE user_id = ?
        """,
        (user_id,),
    )

    # ------------------------------------------------------
    # Cleanup test user
    # ------------------------------------------------------

    execute_query(
        """
        DELETE FROM users
        WHERE id = ?
        """,
        (user_id,),
    )

    # ------------------------------------------------------
    # Verify cleanup
    # ------------------------------------------------------

    remaining = fetch_one(
        """
        SELECT id
        FROM users
        WHERE email = ?
           OR phone = ?
        LIMIT 1
        """,
        (
            test_email,
            test_phone,
        ),
    )

    print(
        "Test cleanup      :",
        "PASS" if not remaining else "FAIL",
    )

    print("=" * 60)
    print("RSA DRIVER DASHBOARD TEST COMPLETE")
    print("=" * 60)


# ==========================================================
# MODULE ENTRY POINT
# ==========================================================

if __name__ == "__main__":
    run_tests()