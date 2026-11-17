"""
RSA - ROADSIDE ASSISTANCE SYSTEM
================================

Main application entry point.

Modules:
    1. Driver
    2. Service Provider
    3. Administrator
    4. Application Information
    0. Exit
"""


# ==========================================================
# APPLICATION INFORMATION
# ==========================================================

APP_NAME = "RSA - Roadside Assistance System"
APP_VERSION = "1.0.0"


def application_info():
    """
    Display RSA application information.
    """

    print()
    print("=" * 60)
    print("RSA - APPLICATION INFORMATION")
    print("=" * 60)

    print()
    print("Application Name : RSA - Roadside Assistance System")
    print("Version          :", APP_VERSION)
    print("System Type      : Roadside Assistance Management")
    print()
    print("Main Modules:")
    print("  • Driver Management")
    print("  • Service Provider Management")
    print("  • Administrator Management")
    print("  • Vehicle Management")
    print("  • Assistance Requests")
    print("  • AI Diagnosis")
    print("  • Incident Analysis")
    print("  • Safety Risk Assessment")
    print("  • Provider Matching")
    print("  • Job Management")
    print("  • Dashboard & Analytics")
    print()
    print("RSA helps drivers report roadside problems,")
    print("analyze incidents and connect with suitable")
    print("roadside assistance providers.")
    print()
    print("=" * 60)

    input("Press Enter to return to the main menu...")


# ==========================================================
# DRIVER
# ==========================================================

def run_driver():
    """
    Open the Driver dashboard.
    """

    try:

        from driver import dashboard

        dashboard.main()

    except ImportError as error:

        print()
        print("=" * 60)
        print("DRIVER MODULE ERROR")
        print("=" * 60)
        print(error)
        print("=" * 60)

        input("Press Enter to return to the main menu...")

    except AttributeError:

        print()
        print("=" * 60)
        print("DRIVER DASHBOARD ERROR")
        print("=" * 60)
        print(
            "driver/dashboard.py does not contain "
            "a main() function."
        )
        print("=" * 60)

        input("Press Enter to return to the main menu...")

    except Exception as error:

        print()
        print("=" * 60)
        print("DRIVER MODULE ERROR")
        print("=" * 60)
        print(error)
        print("=" * 60)

        input("Press Enter to return to the main menu...")


# ==========================================================
# PROVIDER
# ==========================================================

def run_provider():
    """
    Open the Provider dashboard.
    """

    try:

        from provider import dashboard

        dashboard.main()

    except ImportError as error:

        print()
        print("=" * 60)
        print("PROVIDER MODULE ERROR")
        print("=" * 60)
        print(error)
        print("=" * 60)

        input("Press Enter to return to the main menu...")

    except AttributeError:

        print()
        print("=" * 60)
        print("PROVIDER DASHBOARD ERROR")
        print("=" * 60)
        print(
            "provider/dashboard.py does not contain "
            "a main() function."
        )
        print("=" * 60)

        input("Press Enter to return to the main menu...")

    except Exception as error:

        print()
        print("=" * 60)
        print("PROVIDER MODULE ERROR")
        print("=" * 60)
        print(error)
        print("=" * 60)

        input("Press Enter to return to the main menu...")


# ==========================================================
# ADMINISTRATOR
# ==========================================================

def run_admin():
    """
    Open the Administrator dashboard.
    """

    try:

        from admin import dashboard

        dashboard.main()

    except ImportError as error:

        print()
        print("=" * 60)
        print("ADMIN MODULE ERROR")
        print("=" * 60)
        print(error)
        print("=" * 60)

        input("Press Enter to return to the main menu...")

    except AttributeError:

        print()
        print("=" * 60)
        print("ADMIN DASHBOARD ERROR")
        print("=" * 60)
        print(
            "admin/dashboard.py does not contain "
            "a main() function."
        )
        print("=" * 60)

        input("Press Enter to return to the main menu...")

    except Exception as error:

        print()
        print("=" * 60)
        print("ADMIN MODULE ERROR")
        print("=" * 60)
        print(error)
        print("=" * 60)

        input("Press Enter to return to the main menu...")


# ==========================================================
# MAIN MENU
# ==========================================================

def show_menu():
    """
    Display the RSA main menu.
    """

    print()
    print("=" * 60)
    print("RSA - ROADSIDE ASSISTANCE SYSTEM")
    print("=" * 60)

    print()
    print("1. Driver")
    print("2. Service Provider")
    print("3. Administrator")
    print("4. Application Information")
    print("0. Exit")

    print()
    print("=" * 60)


# ==========================================================
# MAIN APPLICATION
# ==========================================================

def main():
    """
    Start the RSA application.
    """

    while True:

        show_menu()

        choice = input(
            "Enter your choice: "
        ).strip()

        # --------------------------------------------------
        # DRIVER
        # --------------------------------------------------

        if choice == "1":

            run_driver()

        # --------------------------------------------------
        # PROVIDER
        # --------------------------------------------------

        elif choice == "2":

            run_provider()

        # --------------------------------------------------
        # ADMINISTRATOR
        # --------------------------------------------------

        elif choice == "3":

            run_admin()

        # --------------------------------------------------
        # APPLICATION INFORMATION
        # --------------------------------------------------

        elif choice == "4":

            application_info()

        # --------------------------------------------------
        # EXIT
        # --------------------------------------------------

        elif choice == "0":

            print()
            print("=" * 60)
            print("Thank you for using RSA.")
            print("Exiting...")
            print("=" * 60)

            break

        # --------------------------------------------------
        # INVALID CHOICE
        # --------------------------------------------------

        else:

            print()
            print("Invalid choice.")
            print(
                "Please select 1, 2, 3, 4, or 0."
            )


# ==========================================================
# ENTRY POINT
# ==========================================================

if __name__ == "__main__":
    main()