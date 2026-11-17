"""
RSA - Administrator Package
"""

PACKAGE_NAME = "RSA Administrator"
PACKAGE_VERSION = "1.0.0"


def get_admin_info():
    return {
        "name": PACKAGE_NAME,
        "version": PACKAGE_VERSION,
        "status": "active"
    }


def show_admin_menu():
    print()
    print("=" * 60)
    print("RSA - ADMINISTRATOR")
    print("=" * 60)
    print()
    print("1. User Management")
    print("2. Provider Management")
    print("3. Analytics")
    print("4. Admin Dashboard")
    print("0. Back to Main Menu")
    print("=" * 60)


def run_module(module_name):
    """Run an admin module safely."""

    try:
        if module_name == "users":
            from . import users
            if hasattr(users, "main"):
                users.main()
            elif hasattr(users, "manage_users"):
                users.manage_users()
            else:
                print("\nUser Management module loaded successfully.")
                print("No main function found.")

        elif module_name == "providers":
            from . import providers
            if hasattr(providers, "main"):
                providers.main()
            elif hasattr(providers, "manage_providers"):
                providers.manage_providers()
            else:
                print("\nProvider Management module loaded successfully.")
                print("No main function found.")

        elif module_name == "analytics":
            from . import analytics
            if hasattr(analytics, "main"):
                analytics.main()
            elif hasattr(analytics, "show_analytics"):
                analytics.show_analytics()
            else:
                print("\nAnalytics module loaded successfully.")
                print("No main function found.")

        elif module_name == "dashboard":
            from . import dashboard
            if hasattr(dashboard, "main"):
                dashboard.main()
            elif hasattr(dashboard, "show_dashboard"):
                dashboard.show_dashboard()
            else:
                print("\nDashboard module loaded successfully.")
                print("No main function found.")

    except Exception as e:
        print()
        print("ADMIN MODULE ERROR")
        print("-" * 40)
        print(f"Error: {e}")


def main():
    """Administrator main menu."""

    while True:

        show_admin_menu()

        choice = input("Enter your choice: ").strip()

        if choice == "1":
            run_module("users")

        elif choice == "2":
            run_module("providers")

        elif choice == "3":
            run_module("analytics")

        elif choice == "4":
            run_module("dashboard")

        elif choice == "0":
            print("\nReturning to RSA Main Menu...")
            break

        else:
            print("\nInvalid choice.")
            print("Please enter 0, 1, 2, 3 or 4.")


if __name__ == "__main__":
    main()