"""
RSA Provider Dashboard
----------------------
Provider-side dashboard for Roadside Assistance System.

This module handles:
    - Provider login / identification
    - Provider profile
    - Dashboard summary
    - Assistance requests
    - Pending requests
    - Active jobs
    - Job details
    - Job status updates
    - Logout
"""

from database.database import execute_query, fetch_one, fetch_all

from provider.requests import (
    get_request_by_id,
    get_provider_requests,
    get_pending_requests,
    update_request_status,
    accept_request,
    mark_arrived,
    start_service,
    complete_request,
    cancel_request,
    get_request_summary,
)


# ================================================================
# CONSTANTS
# ================================================================

LINE = "=" * 65
SMALL_LINE = "-" * 65


# ================================================================
# BASIC UI HELPERS
# ================================================================

def line(char="="):
    print(char * 65)


def pause(message="Press Enter to continue..."):
    input(f"\n{message}")


def clear_screen():
    """
    Simple console screen clear.
    """
    print("\n" * 3)


def print_header(title):
    print()
    line("=")
    print(title.center(65))
    line("=")


# ================================================================
# PROVIDER
# ================================================================

def get_provider(provider_id):
    """
    Get provider information.

    Provider table structure used by the RSA project:
        id
        user_id
        business_name
        service_type
        phone
        availability
    """

    return fetch_one(
        """
        SELECT
            p.id,
            p.user_id,
            p.business_name,
            p.service_type,
            p.phone,
            p.availability,

            u.name AS user_name,
            u.email AS user_email

        FROM providers p

        LEFT JOIN users u
            ON p.user_id = u.id

        WHERE p.id = ?
        """,
        (provider_id,),
    )


def get_provider_id():
    """
    Ask the user for provider ID.
    """

    while True:

        value = input("\nEnter Provider ID: ").strip()

        try:
            provider_id = int(value)

            if provider_id <= 0:
                print("Provider ID must be greater than 0.")
                continue

            return provider_id

        except ValueError:
            print("Please enter a valid numeric Provider ID.")


def print_provider(provider):
    """
    Display provider information.
    """

    if not provider:
        print("Provider information unavailable.")
        return

    print_header("PROVIDER INFORMATION")

    print(f"Provider ID     : {provider['id']}")
    print(f"Name            : {provider['user_name'] or 'N/A'}")
    print(f"Business Name   : {provider['business_name'] or 'N/A'}")
    print(f"Service Type    : {provider['service_type'] or 'N/A'}")
    print(f"Phone           : {provider['phone'] or 'N/A'}")
    print(f"Email           : {provider['user_email'] or 'N/A'}")
    print(f"Availability    : {provider['availability'] or 'N/A'}")

    line("-")


def print_profile(provider_id):
    """
    Display provider profile.
    """

    provider = get_provider(provider_id)

    if not provider:
        print("\nPROVIDER NOT FOUND")
        print(LINE)
        print(f"No provider exists with ID {provider_id}.")
        return

    print_provider(provider)


# ================================================================
# DASHBOARD SUMMARY
# ================================================================

def get_dashboard_summary(provider_id):
    """
    Return dashboard statistics.

    This function intentionally uses service_matches because
    provider requests are connected to providers through
    service_matches.
    """

    try:

        row = fetch_one(
            """
            SELECT

                COUNT(*) AS total_requests,

                SUM(
                    CASE
                        WHEN sm.status = 'COMPLETED'
                        THEN 1
                        ELSE 0
                    END
                ) AS completed_requests,

                SUM(
                    CASE
                        WHEN sm.status = 'CANCELLED'
                        THEN 1
                        ELSE 0
                    END
                ) AS cancelled_requests,

                SUM(
                    CASE
                        WHEN sm.status IN (
                            'MATCHED',
                            'ASSIGNED',
                            'ACCEPTED',
                            'ON_THE_WAY',
                            'ARRIVED',
                            'IN_PROGRESS'
                        )
                        THEN 1
                        ELSE 0
                    END
                ) AS active_requests,

                SUM(
                    CASE
                        WHEN sm.status IN (
                            'MATCHED',
                            'ASSIGNED'
                        )
                        THEN 1
                        ELSE 0
                    END
                ) AS pending_requests

            FROM service_matches sm

            WHERE sm.provider_id = ?
            """,
            (provider_id,),
        )

        if not row:
            return {
                "total_requests": 0,
                "completed_requests": 0,
                "cancelled_requests": 0,
                "active_requests": 0,
                "pending_requests": 0,
            }

        return {
            "total_requests": row["total_requests"] or 0,
            "completed_requests": row["completed_requests"] or 0,
            "cancelled_requests": row["cancelled_requests"] or 0,
            "active_requests": row["active_requests"] or 0,
            "pending_requests": row["pending_requests"] or 0,
        }

    except Exception as error:

        print(f"\nUnable to load dashboard summary: {error}")

        return {
            "total_requests": 0,
            "completed_requests": 0,
            "cancelled_requests": 0,
            "active_requests": 0,
            "pending_requests": 0,
        }


def get_provider_dashboard(provider_id):
    """
    Compatibility function.

    Some RSA modules may import get_provider_dashboard().
    """

    provider = get_provider(provider_id)
    summary = get_dashboard_summary(provider_id)

    return {
        "provider": provider,
        "summary": summary,
    }


def print_dashboard_summary(provider_id):
    """
    Print dashboard statistics.
    """

    summary = get_dashboard_summary(provider_id)

    print_header("PROVIDER DASHBOARD")

    print(f"Total Requests       : {summary['total_requests']}")
    print(f"Pending Requests     : {summary['pending_requests']}")
    print(f"Active Requests      : {summary['active_requests']}")
    print(f"Completed Requests   : {summary['completed_requests']}")
    print(f"Cancelled Requests   : {summary['cancelled_requests']}")

    line("-")


# ================================================================
# REQUEST DISPLAY
# ================================================================

def print_request(request):
    """
    Print one assistance request.
    """

    print(SMALL_LINE)

    print(f"Request ID       : {request['id']}")
    print(f"Incident Type    : {request['incident_type'] or 'N/A'}")
    print(f"Priority         : {request['priority'] or 'N/A'}")
    print(f"Status           : {request['status'] or 'N/A'}")

    print(
        f"Recommended      : "
        f"{request['recommended_service'] or 'N/A'}"
    )

    print(
        f"Escalation       : "
        f"{request['escalation'] or 'N/A'}"
    )

    print(
        f"Safe To Drive    : "
        f"{request['safe_to_drive'] or 'N/A'}"
    )

    print(f"Customer         : {request['user_name'] or 'N/A'}")
    print(f"Phone            : {request['user_phone'] or 'N/A'}")

    if request.get("registration_number"):
        print(
            f"Vehicle          : "
            f"{request['registration_number']} "
            f"{request.get('make') or ''} "
            f"{request.get('model') or ''}"
        )

    print(
        f"Location         : "
        f"{request['latitude']}, {request['longitude']}"
    )

    if request.get("description"):
        print(f"Description      : {request['description']}")

    if request.get("match_id"):
        print(f"Match ID         : {request['match_id']}")

    if request.get("match_score") is not None:
        print(f"Match Score      : {request['match_score']}")

    if request.get("distance_km") is not None:
        print(f"Distance         : {request['distance_km']} km")

    if request.get("match_status"):
        print(f"Match Status     : {request['match_status']}")

    print(SMALL_LINE)


# ================================================================
# ALL REQUESTS
# ================================================================

def print_requests(provider_id):
    """
    Display all requests assigned/matched to provider.
    """

    print_header("ALL ASSISTANCE REQUESTS")

    try:
        requests = get_provider_requests(provider_id)

    except Exception as error:
        print(f"Unable to load requests: {error}")
        return

    if not requests:
        print("No assistance requests found.")
        return

    print(f"Total Requests: {len(requests)}")

    for request in requests:
        print_request(request)


# ================================================================
# PENDING REQUESTS
# ================================================================

def print_pending_requests(provider_id):
    """
    Display pending requests.
    """

    print_header("PENDING REQUESTS")

    try:
        requests = get_pending_requests(provider_id)

    except Exception as error:
        print(f"Unable to load pending requests: {error}")
        return

    if not requests:
        print("No pending requests.")
        return

    print(f"Pending Requests: {len(requests)}")

    for request in requests:
        print_request(request)


# ================================================================
# REQUEST DETAILS
# ================================================================

def print_request_details(request_id):
    """
    Display complete request details.
    """

    request = get_request_by_id(request_id)

    if not request:
        print("\nREQUEST NOT FOUND")
        return

    print_header("ASSISTANCE REQUEST DETAILS")

    print(f"Request ID       : {request['id']}")
    print(f"User ID          : {request['user_id']}")
    print(f"Vehicle ID       : {request['vehicle_id']}")
    print(f"Customer         : {request['user_name']}")
    print(f"Email            : {request['user_email']}")
    print(f"Phone            : {request['user_phone']}")

    print(SMALL_LINE)

    print(f"Incident Type    : {request['incident_type']}")
    print(f"Priority         : {request['priority']}")
    print(f"Description      : {request['description']}")
    print(f"Recommended      : {request['recommended_service']}")
    print(f"Escalation       : {request['escalation']}")
    print(f"Safe To Drive    : {request['safe_to_drive']}")
    print(f"Status           : {request['status']}")

    print(SMALL_LINE)

    print(f"Latitude         : {request['latitude']}")
    print(f"Longitude        : {request['longitude']}")

    print(SMALL_LINE)

    print(f"Created At       : {request['created_at']}")
    print(f"Updated At       : {request['updated_at']}")

    if request.get("registration_number"):

        print(SMALL_LINE)

        print("VEHICLE")

        print(
            f"Registration     : "
            f"{request['registration_number']}"
        )

        print(f"Make             : {request['make']}")
        print(f"Model            : {request['model']}")
        print(f"Year             : {request['year']}")
        print(f"Fuel Type        : {request['fuel_type']}")


# ================================================================
# ACTIVE JOBS
# ================================================================

def get_active_jobs(provider_id):
    """
    Return active jobs for a provider.

    Jobs are derived from service_matches and assistance_requests.
    This keeps the dashboard compatible with the existing request
    workflow.
    """

    return fetch_all(
        """
        SELECT
            ar.id,
            ar.user_id,
            ar.vehicle_id,
            ar.incident_type,
            ar.description,
            ar.priority,
            ar.status,
            ar.latitude,
            ar.longitude,
            ar.created_at,

            sm.id AS match_id,
            sm.match_score,
            sm.distance_km,
            sm.status AS match_status,

            u.name AS user_name,
            u.phone AS user_phone,

            v.registration_number,
            v.make,
            v.model

        FROM assistance_requests ar

        JOIN service_matches sm
            ON ar.id = sm.request_id

        JOIN users u
            ON ar.user_id = u.id

        LEFT JOIN vehicles v
            ON ar.vehicle_id = v.id

        WHERE sm.provider_id = ?

        AND sm.status NOT IN (
            'COMPLETED',
            'CANCELLED'
        )

        ORDER BY
            CASE ar.priority
                WHEN 'CRITICAL' THEN 1
                WHEN 'HIGH' THEN 2
                WHEN 'MEDIUM' THEN 3
                WHEN 'LOW' THEN 4
                ELSE 5
            END,
            ar.created_at ASC
        """,
        (provider_id,),
    )


def print_active_jobs(provider_id):
    """
    Display active provider jobs.
    """

    print_header("ACTIVE JOBS")

    try:
        jobs = get_active_jobs(provider_id)

    except Exception as error:
        print(f"Unable to load active jobs: {error}")
        return

    if not jobs:
        print("No active jobs.")
        return

    print(f"Active Jobs: {len(jobs)}")

    for job in jobs:
        print_request(job)


# ================================================================
# JOB DETAILS
# ================================================================

def get_job_details(job_id, provider_id=None):
    """
    Get job details.

    A job corresponds to an assistance request matched to a provider.
    """

    query = """
        SELECT
            ar.id,
            ar.user_id,
            ar.vehicle_id,
            ar.incident_type,
            ar.description,
            ar.priority,
            ar.recommended_service,
            ar.escalation,
            ar.safe_to_drive,
            ar.status,
            ar.latitude,
            ar.longitude,
            ar.created_at,
            ar.updated_at,

            sm.id AS match_id,
            sm.provider_id,
            sm.match_score,
            sm.distance_km,
            sm.status AS match_status,

            u.name AS user_name,
            u.email AS user_email,
            u.phone AS user_phone,

            v.registration_number,
            v.make,
            v.model,
            v.year,
            v.fuel_type

        FROM assistance_requests ar

        JOIN service_matches sm
            ON ar.id = sm.request_id

        JOIN users u
            ON ar.user_id = u.id

        LEFT JOIN vehicles v
            ON ar.vehicle_id = v.id

        WHERE sm.id = ?
    """

    return fetch_one(query, (job_id,))


def print_job_details(job_id, provider_id=None):
    """
    Display complete job information.
    """

    job = get_job_details(job_id, provider_id)

    if not job:
        print("\nJOB NOT FOUND")
        return

    print_header("JOB DETAILS")

    print(f"Job / Match ID   : {job['match_id']}")
    print(f"Request ID       : {job['id']}")
    print(f"Provider ID      : {job['provider_id']}")

    print(SMALL_LINE)

    print(f"Customer         : {job['user_name']}")
    print(f"Email            : {job['user_email']}")
    print(f"Phone            : {job['user_phone']}")

    print(SMALL_LINE)

    print(f"Incident Type    : {job['incident_type']}")
    print(f"Priority         : {job['priority']}")
    print(f"Description      : {job['description']}")
    print(f"Request Status   : {job['status']}")
    print(f"Match Status     : {job['match_status']}")

    print(SMALL_LINE)

    print(f"Latitude         : {job['latitude']}")
    print(f"Longitude        : {job['longitude']}")

    print(SMALL_LINE)

    print(f"Match Score      : {job['match_score']}")
    print(f"Distance         : {job['distance_km']} km")

    if job.get("registration_number"):

        print(SMALL_LINE)

        print("VEHICLE")

        print(
            f"Registration     : "
            f"{job['registration_number']}"
        )

        print(f"Make             : {job['make']}")
        print(f"Model            : {job['model']}")
        print(f"Year             : {job['year']}")
        print(f"Fuel Type        : {job['fuel_type']}")


# ================================================================
# JOB STATUS
# ================================================================

def update_job_status(
    job_id,
    status,
    provider_id=None,
):
    """
    Update job/match status and main assistance request status.
    """

    if not isinstance(status, str):
        return {
            "success": False,
            "message": "Status must be a string.",
        }

    status = status.strip().upper()

    allowed_statuses = {
        "MATCHED",
        "ASSIGNED",
        "ACCEPTED",
        "ON_THE_WAY",
        "ARRIVED",
        "IN_PROGRESS",
        "COMPLETED",
        "CANCELLED",
    }

    if status not in allowed_statuses:
        return {
            "success": False,
            "message": "Invalid job status.",
        }

    job = get_job_details(job_id, provider_id)

    if not job:
        return {
            "success": False,
            "message": "Job not found.",
        }

    if provider_id is not None:

        if int(job["provider_id"]) != int(provider_id):
            return {
                "success": False,
                "message": "This job does not belong to the provider.",
            }

    # Delegate to the shared lifecycle state machine (validated transitions,
    # one transaction for match + request + tracking).
    from assistance.lifecycle import LifecycleError, transition_match

    target = status
    note = None
    if status in ("MATCHED", "ASSIGNED"):
        return {
            "success": False,
            "message": "This status is set by the matching engine, not by a provider.",
        }
    if status == "CANCELLED":
        note = "Withdrawn from the provider console."
        target = "REJECTED" if (job["match_status"] or "").upper() == "ASSIGNED" else "UNABLE_TO_COMPLETE"

    try:
        result = transition_match(job_id, target, provider_id=job["provider_id"], note=note)
    except LifecycleError as error:
        return {
            "success": False,
            "message": error.message,
        }
    except Exception as error:
        return {
            "success": False,
            "message": f"Job status update failed: {error}",
        }

    return {
        "success": True,
        "message": "Job status updated successfully.",
        "job_id": job_id,
        "request_id": job["id"],
        "status": result["status"],
    }


# ================================================================
# JOB STATUS MENU
# ================================================================

def change_job_status(provider_id):
    """
    Interactive job status update.
    """

    print_header("UPDATE JOB STATUS")

    try:
        job_id = int(
            input("Enter Match / Job ID: ").strip()
        )
    except ValueError:
        print("Invalid Job ID.")
        return

    job = get_job_details(job_id, provider_id)

    if not job:
        print("Job not found.")
        return

    print()
    print(f"Current Status: {job['match_status']}")

    print()
    print("1. ACCEPTED")
    print("2. ON_THE_WAY")
    print("3. ARRIVED")
    print("4. IN_PROGRESS")
    print("5. COMPLETED")
    print("6. CANCELLED")
    print("0. Back")

    choice = input("\nSelect status: ").strip()

    status_map = {
        "1": "ACCEPTED",
        "2": "ON_THE_WAY",
        "3": "ARRIVED",
        "4": "IN_PROGRESS",
        "5": "COMPLETED",
        "6": "CANCELLED",
    }

    if choice == "0":
        return

    if choice not in status_map:
        print("Invalid choice.")
        return

    result = update_job_status(
        job_id,
        status_map[choice],
        provider_id,
    )

    print()
    print(result["message"])


# ================================================================
# ACCEPT REQUEST
# ================================================================

def accept_provider_request(provider_id):
    """
    Accept a pending assistance request.
    """

    print_header("ACCEPT REQUEST")

    try:
        request_id = int(
            input("Enter Request ID: ").strip()
        )
    except ValueError:
        print("Invalid Request ID.")
        return

    requests = get_pending_requests(provider_id)

    selected = None

    for request in requests:

        if int(request["id"]) == request_id:
            selected = request
            break

    if not selected:

        print()
        print("Request is not assigned to this provider")
        print("or it is no longer pending.")

        return

    result = accept_request(request_id)

    print()
    print(result["message"])


# ================================================================
# ARRIVED
# ================================================================

def provider_mark_arrived(provider_id):

    print_header("MARK ARRIVED")

    try:
        request_id = int(
            input("Enter Request ID: ").strip()
        )
    except ValueError:
        print("Invalid Request ID.")
        return

    result = mark_arrived(request_id)

    print()
    print(result["message"])


# ================================================================
# START SERVICE
# ================================================================

def provider_start_service(provider_id):

    print_header("START SERVICE")

    try:
        request_id = int(
            input("Enter Request ID: ").strip()
        )
    except ValueError:
        print("Invalid Request ID.")
        return

    result = start_service(request_id)

    print()
    print(result["message"])


# ================================================================
# COMPLETE SERVICE
# ================================================================

def provider_complete_request(provider_id):

    print_header("COMPLETE REQUEST")

    try:
        request_id = int(
            input("Enter Request ID: ").strip()
        )
    except ValueError:
        print("Invalid Request ID.")
        return

    result = complete_request(request_id)

    print()
    print(result["message"])


# ================================================================
# CANCEL REQUEST
# ================================================================

def provider_cancel_request(provider_id):

    print_header("CANCEL REQUEST")

    try:
        request_id = int(
            input("Enter Request ID: ").strip()
        )
    except ValueError:
        print("Invalid Request ID.")
        return

    result = cancel_request(request_id)

    print()
    print(result["message"])


# ================================================================
# REQUEST DETAILS MENU
# ================================================================

def view_request_details():

    print_header("VIEW REQUEST")

    try:
        request_id = int(
            input("Enter Request ID: ").strip()
        )
    except ValueError:
        print("Invalid Request ID.")
        return

    print_request_details(request_id)


# ================================================================
# JOB DETAILS MENU
# ================================================================

def view_job_details(provider_id):

    print_header("VIEW JOB")

    try:
        job_id = int(
            input("Enter Match / Job ID: ").strip()
        )
    except ValueError:
        print("Invalid Job ID.")
        return

    job = get_job_details(job_id, provider_id)

    if not job:
        print("Job not found.")
        return

    print_job_details(job_id, provider_id)


# ================================================================
# DASHBOARD HOME
# ================================================================

def dashboard_home(provider_id):

    provider = get_provider(provider_id)

    if not provider:
        print()
        line("=")
        print("PROVIDER NOT FOUND")
        line("=")
        print(f"No provider exists with ID {provider_id}.")
        return False

    print()
    line("=")
    print("RSA PROVIDER DASHBOARD".center(65))
    line("=")

    print(
        f"Welcome, "
        f"{provider['business_name'] or provider['user_name']}"
    )

    print(
        f"Provider ID: {provider['id']}"
    )

    print()

    summary = get_dashboard_summary(provider_id)

    print(f"Total Requests     : {summary['total_requests']}")
    print(f"Pending Requests   : {summary['pending_requests']}")
    print(f"Active Jobs        : {summary['active_requests']}")
    print(f"Completed          : {summary['completed_requests']}")
    print(f"Cancelled          : {summary['cancelled_requests']}")

    line("-")

    return True


# ================================================================
# MAIN PROVIDER MENU
# ================================================================

def main():
    """
    Main entry point used by app.py.

    app.py calls:

        dashboard.main()

    """

    provider_id = get_provider_id()

    provider = get_provider(provider_id)

    if not provider:

        print()
        line("=")
        print("PROVIDER NOT FOUND".center(65))
        line("=")
        print(f"No provider exists with ID {provider_id}.")
        line("=")

        pause()

        return

    while True:

        clear_screen()

        dashboard_home(provider_id)

        print()
        print("1. View All Requests")
        print("2. View Pending Requests")
        print("3. View Active Jobs")
        print("4. View Request Details")
        print("5. View Job Details")
        print("6. Accept Request")
        print("7. Mark Arrived")
        print("8. Start Service")
        print("9. Complete Request")
        print("10. Cancel Request")
        print("11. Update Job Status")
        print("12. View Provider Profile")
        print("13. Refresh Dashboard")
        print("0. Logout")

        print()

        choice = input("Enter your choice: ").strip()

        # --------------------------------------------------------
        # REQUESTS
        # --------------------------------------------------------

        if choice == "1":

            print_requests(provider_id)
            pause()

        elif choice == "2":

            print_pending_requests(provider_id)
            pause()

        # --------------------------------------------------------
        # JOBS
        # --------------------------------------------------------

        elif choice == "3":

            print_active_jobs(provider_id)
            pause()

        elif choice == "4":

            view_request_details()
            pause()

        elif choice == "5":

            view_job_details(provider_id)
            pause()

        # --------------------------------------------------------
        # REQUEST ACTIONS
        # --------------------------------------------------------

        elif choice == "6":

            accept_provider_request(provider_id)
            pause()

        elif choice == "7":

            provider_mark_arrived(provider_id)
            pause()

        elif choice == "8":

            provider_start_service(provider_id)
            pause()

        elif choice == "9":

            provider_complete_request(provider_id)
            pause()

        elif choice == "10":

            provider_cancel_request(provider_id)
            pause()

        # --------------------------------------------------------
        # JOB STATUS
        # --------------------------------------------------------

        elif choice == "11":

            change_job_status(provider_id)
            pause()

        # --------------------------------------------------------
        # PROFILE
        # --------------------------------------------------------

        elif choice == "12":

            print_profile(provider_id)
            pause()

        # --------------------------------------------------------
        # REFRESH
        # --------------------------------------------------------

        elif choice == "13":

            continue

        # --------------------------------------------------------
        # LOGOUT
        # --------------------------------------------------------

        elif choice == "0":

            print()
            print("Logging out from Provider Dashboard...")
            return

        # --------------------------------------------------------
        # INVALID
        # --------------------------------------------------------

        else:

            print()
            print("Invalid choice.")
            print("Please select a valid option.")
            pause()


# ================================================================
# TESTS
# ================================================================

def run_tests():

    print("=" * 65)
    print("RSA PROVIDER DASHBOARD TEST")
    print("=" * 65)

    print("Module import        : PASS")

    functions = [
        line,
        pause,
        clear_screen,
        print_header,
        get_provider,
        get_provider_id,
        print_provider,
        print_profile,
        get_dashboard_summary,
        get_provider_dashboard,
        print_dashboard_summary,
        print_request,
        print_requests,
        print_pending_requests,
        print_request_details,
        get_active_jobs,
        print_active_jobs,
        get_job_details,
        print_job_details,
        update_job_status,
        change_job_status,
        accept_provider_request,
        provider_mark_arrived,
        provider_start_service,
        provider_complete_request,
        provider_cancel_request,
        view_request_details,
        view_job_details,
        dashboard_home,
        main,
    ]

    print(
        "Functions loaded     :",
        "PASS"
        if all(callable(fn) for fn in functions)
        else "FAIL"
    )

    # Test with a deliberately invalid provider.
    summary = get_dashboard_summary(999999)

    print(
        "Summary function     :",
        "PASS"
        if isinstance(summary, dict)
        else "FAIL"
    )

    dashboard = get_provider_dashboard(999999)

    print(
        "Dashboard function   :",
        "PASS"
        if isinstance(dashboard, dict)
        else "FAIL"
    )

    print("=" * 65)
    print("RSA PROVIDER DASHBOARD TEST COMPLETE")
    print("=" * 65)


# ================================================================
# ENTRY POINT
# ================================================================

if __name__ == "__main__":
    run_tests()