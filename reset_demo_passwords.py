
"""
Set known passwords for the four RSA demo accounts (development only).

    python reset_demo_passwords.py            set the passwords
    python reset_demo_passwords.py --check    check which passwords currently work
    python reset_demo_passwords.py --ensure   fix only accounts whose password does not work

- Only touches the demo accounts listed below.
- Re-activates them and clears failed-login lockouts.
- Refuses to run when RSA_ENV=production.
"""

import os
import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_DIR))
os.chdir(PROJECT_DIR)

from authentication.password import hash_password, verify_password  # noqa: E402
from database.database import execute_query, fetch_one, get_database_path  # noqa: E402
from database.migrations import backup_database, migrate  # noqa: E402
from database.models import create_tables  # noqa: E402

DEMO_ACCOUNTS = {
    "admin@rsa.local": os.environ.get("RSA_DEMO_ADMIN_PASSWORD"),
    "driver.demo@rsa.local": os.environ.get("RSA_DEMO_DRIVER_PASSWORD"),
    "provider.demo@rsa.local": os.environ.get("RSA_DEMO_PROVIDER_PASSWORD"),
    "provider@rsa.local": os.environ.get("RSA_DEMO_PROVIDER2_PASSWORD"),
}


def _status(email, password):
    if not password:
        return "NOT CONFIGURED", None

    user = fetch_one(
        "SELECT password_hash, is_active, role FROM users WHERE email = ?",
        (email,)
    )

    if not user:
        return "MISSING", None

    works = verify_password(password, user["password_hash"])

    if works and user["is_active"]:
        return "OK", user["role"]

    return ("INACTIVE" if works else "NOT SET"), user["role"]


def check(verbose=True):
    ok = True

    for email, password in DEMO_ACCOUNTS.items():
        state, role = _status(email, password)
        ok = ok and state == "OK"

        if verbose:
            print(f"  {state:14s} {role or '':9s} {email}")

    return ok


def _require_demo_passwords():
    missing = [
        email for email, password in DEMO_ACCOUNTS.items()
        if not password
    ]

    if missing:
        sys.exit(
            "Demo passwords are not configured. "
            "Set RSA_DEMO_ADMIN_PASSWORD, "
            "RSA_DEMO_DRIVER_PASSWORD, "
            "RSA_DEMO_PROVIDER_PASSWORD, and "
            "RSA_DEMO_PROVIDER2_PASSWORD."
        )


def _prepare():
    if os.environ.get("RSA_ENV", "").strip().lower() == "production":
        sys.exit("Refusing to reset demo passwords in production.")

    db_path = get_database_path()

    if not Path(db_path).exists():
        sys.exit(
            f"Database file not found: {db_path}\n"
            "Run this from the folder that contains rsa.db."
        )

    create_tables()
    migrate()

    return db_path


def reset(only_broken=False):
    """Reset demo passwords (all, or only those that do not work)."""
    _require_demo_passwords()

    to_fix = [
        email for email, pw in DEMO_ACCOUNTS.items()
        if not only_broken
        or _status(email, pw)[0] in ("NOT SET", "INACTIVE")
    ]

    to_fix = [
        email for email in to_fix
        if fetch_one("SELECT 1 FROM users WHERE email = ?", (email,))
    ]

    if to_fix:
        backup = backup_database(
            get_database_path(),
            label="pre-demo-reset"
        )
        print(f"Backup written : {backup}")

        for email in to_fix:
            execute_query(
                "UPDATE users SET password_hash = ?, is_active = 1 WHERE email = ?",
                (hash_password(DEMO_ACCOUNTS[email]), email)
            )

    execute_query("DELETE FROM login_attempts WHERE success = 0")

    return len(to_fix)


def ensure_demo_passwords():
    """Used by run_rsa.py to make sure demo logins work."""
    db_path = _prepare()

    print(f"Project folder : {PROJECT_DIR}")
    print(f"Database file  : {db_path}")

    changed = reset(only_broken=True)

    if changed:
        print(f"Fixed {changed} demo login(s).")

    print("Demo sign-in details:")
    return check()


def main():
    db_path = _prepare()

    print(f"Project folder : {PROJECT_DIR}")
    print(f"Database file  : {db_path}")

    if os.environ.get("RSA_DATABASE_PATH"):
        print(
            "  (RSA_DATABASE_PATH is set, "
            "so this file is used instead of the project's rsa.db)"
        )

    if "--check" in sys.argv:
        print("\nCurrent state:")
        check()
        return

    reset(only_broken="--ensure" in sys.argv)

    print("\nVerified sign-in details:")

    if check():
        print(
            f"\nAll set. Start the app from this folder:\n"
            f'  cd "{PROJECT_DIR}"\n'
            "  python run_rsa.py"
        )
        print("Passwords are case-sensitive. Change them before real use.")
    else:
        print("\nSome accounts are missing from this database (see above).")


if __name__ == "__main__":
    main()
