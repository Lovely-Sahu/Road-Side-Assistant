"""
RSA Administrator Dashboard
"""

from admin.users import display_users, get_user_count
from admin.providers import display_providers, get_provider_count
from admin.analytics import display_analytics


def show_dashboard():
    print("\n" + "=" * 60)
    print("RSA - ADMINISTRATOR DASHBOARD")
    print("=" * 60)

    print()
    print("1. User Management")
    print("2. Service Provider Management")
    print("3. System Analytics")
    print("4. Dashboard Summary")
    print("0. Back to Main Menu")

    print("=" * 60)


def dashboard_summary():
    print("\n" + "=" * 60)
    print("RSA - ADMIN DASHBOARD SUMMARY")
    print("=" * 60)

    try:
        users = get_user_count()
    except Exception:
        users = 0

    try:
        providers = get_provider_count()
    except Exception:
        providers = 0

    print()
    print(f"Total Users             : {users}")
    print(f"Total Service Providers : {providers}")

    print("=" * 60)


def main():

    while True:

        show_dashboard()

        choice = input("Enter your choice: ").strip()

        if choice == "1":
            display_users()

        elif choice == "2":
            display_providers()

        elif choice == "3":
            display_analytics()

        elif choice == "4":
            dashboard_summary()

        elif choice == "0":
            print("\nReturning to RSA Main Menu...")
            break

        else:
            print("\nInvalid choice.")
            print("Please enter 0, 1, 2, 3 or 4.")


if __name__ == "__main__":
    main()