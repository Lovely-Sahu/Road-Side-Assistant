"""
RSA Provider Jobs
-----------------
Handles provider job assignment, job lookup,
job status updates and job completion.
"""

from database.database import (
    execute_query,
    fetch_one,
    fetch_all,
)


# ==========================================================
# CONSTANTS
# ==========================================================

VALID_JOB_STATUSES = {
    "ASSIGNED",
    "ACCEPTED",
    "ON_THE_WAY",
    "ARRIVED",
    "IN_PROGRESS",
    "COMPLETED",
    "CANCELLED",
}


# ==========================================================
# JOB LOOKUP
# ==========================================================

def get_job_by_id(job_id: int):
    """
    Return a job by service-match ID.
    """

    if not job_id:
        return None

    return fetch_one(
        """
        SELECT
            sm.id,
            sm.request_id,
            sm.provider_id,
            sm.match_score,
            sm.distance_km,
            sm.status,
            sm.created_at,

            ar.user_id,
            ar.vehicle_id,
            ar.incident_type,
            ar.description,
            ar.priority,
            ar.recommended_service,
            ar.escalation,
            ar.safe_to_drive,
            ar.status AS request_status,
            ar.latitude,
            ar.longitude,
            ar.created_at AS request_created_at,

            p.business_name,
            p.service_type,
            p.phone AS provider_phone

        FROM service_matches sm

        JOIN assistance_requests ar
            ON sm.request_id = ar.id

        JOIN providers p
            ON sm.provider_id = p.id

        WHERE sm.id = ?
        """,
        (job_id,),
    )


def get_provider_jobs(provider_id: int):
    """
    Return all jobs assigned to a provider.
    """

    if not provider_id:
        return []

    return fetch_all(
        """
        SELECT
            sm.id,
            sm.request_id,
            sm.provider_id,
            sm.match_score,
            sm.distance_km,
            sm.status,
            sm.created_at,

            ar.user_id,
            ar.vehicle_id,
            ar.incident_type,
            ar.description,
            ar.priority,
            ar.recommended_service,
            ar.escalation,
            ar.safe_to_drive,
            ar.status AS request_status,
            ar.latitude,
            ar.longitude,
            ar.created_at AS request_created_at

        FROM service_matches sm

        JOIN assistance_requests ar
            ON sm.request_id = ar.id

        WHERE sm.provider_id = ?

        ORDER BY sm.created_at DESC
        """,
        (provider_id,),
    )


def get_active_jobs(provider_id: int):
    """
    Return active jobs for a provider.

    Completed and cancelled jobs are excluded.
    """

    if not provider_id:
        return []

    return fetch_all(
        """
        SELECT
            sm.id,
            sm.request_id,
            sm.provider_id,
            sm.match_score,
            sm.distance_km,
            sm.status,
            sm.created_at,

            ar.user_id,
            ar.vehicle_id,
            ar.incident_type,
            ar.description,
            ar.priority,
            ar.recommended_service,
            ar.escalation,
            ar.safe_to_drive,
            ar.status AS request_status,
            ar.latitude,
            ar.longitude

        FROM service_matches sm

        JOIN assistance_requests ar
            ON sm.request_id = ar.id

        WHERE sm.provider_id = ?

        AND sm.status NOT IN (
            'COMPLETED',
            'CANCELLED'
        )

        ORDER BY sm.created_at DESC
        """,
        (provider_id,),
    )


# ==========================================================
# JOB STATUS VALIDATION
# ==========================================================

def validate_job_status(status: str) -> str:
    """
    Validate and normalize a job status.
    """

    if not isinstance(status, str):
        raise ValueError(
            "Job status must be a string."
        )

    status = status.strip().upper()

    if status not in VALID_JOB_STATUSES:
        raise ValueError(
            "Invalid job status. Allowed values: "
            + ", ".join(sorted(VALID_JOB_STATUSES))
        )

    return status


# ==========================================================
# JOB STATUS UPDATE
# ==========================================================

def update_job_status(
    job_id: int,
    status: str,
):
    """
    Update the status of a provider job.

    The related assistance request status
    is updated at the same time.
    """

    if not job_id:
        return {
            "success": False,
            "message": "Job ID is required.",
        }

    try:

        status = validate_job_status(status)

    except ValueError as error:

        return {
            "success": False,
            "message": str(error),
        }

    job = get_job_by_id(job_id)

    if not job:
        return {
            "success": False,
            "message": "Job not found.",
        }

    # All status changes go through the shared lifecycle state machine so the
    # service match, assistance request and tracking history stay consistent
    # (previously this wrote both tables without any transition validation).
    from assistance.lifecycle import LifecycleError, transition_match

    if status == "ASSIGNED":
        return {
            "success": False,
            "message": "ASSIGNED is set by the matching engine, not by a provider.",
        }

    note = None
    if status == "CANCELLED":
        # A provider withdrawing from a job: reject if not yet accepted,
        # otherwise report it as unable to complete (triggers reassignment).
        note = "Withdrawn from the provider console."
        status = "REJECTED" if job["status"] == "ASSIGNED" else "UNABLE_TO_COMPLETE"

    try:
        result = transition_match(job_id, status, provider_id=job["provider_id"], note=note)
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
        "message": (
            "Status is unchanged."
            if result.get("unchanged")
            else "Job status updated successfully."
        ),
        "job_id": job_id,
        "request_id": job["request_id"],
        "status": result["status"],
    }


# ==========================================================
# ACCEPT JOB
# ==========================================================

def accept_job(job_id: int):
    """
    Accept an assigned job.
    """

    return update_job_status(
        job_id,
        "ACCEPTED",
    )


# ==========================================================
# ON THE WAY
# ==========================================================

def mark_on_the_way(job_id: int):
    """
    Mark provider as being on the way.
    """

    return update_job_status(
        job_id,
        "ON_THE_WAY",
    )


# ==========================================================
# ARRIVED
# ==========================================================

def mark_arrived(job_id: int):
    """
    Mark provider as arrived at the location.
    """

    return update_job_status(
        job_id,
        "ARRIVED",
    )


# ==========================================================
# START JOB
# ==========================================================

def start_job(job_id: int):
    """
    Start a provider job.
    """

    return update_job_status(
        job_id,
        "IN_PROGRESS",
    )


# ==========================================================
# COMPLETE JOB
# ==========================================================

def complete_job(job_id: int):
    """
    Mark a provider job as completed.
    """

    return update_job_status(
        job_id,
        "COMPLETED",
    )


# ==========================================================
# CANCEL JOB
# ==========================================================

def cancel_job(job_id: int):
    """
    Cancel a provider job.
    """

    return update_job_status(
        job_id,
        "CANCELLED",
    )


# ==========================================================
# JOB SUMMARY
# ==========================================================

def get_job_summary(provider_id: int):
    """
    Return provider job statistics.
    """

    if not provider_id:
        return {
            "total_jobs": 0,
            "completed_jobs": 0,
            "cancelled_jobs": 0,
            "active_jobs": 0,
        }

    row = fetch_one(
        """
        SELECT
            COUNT(*) AS total_jobs,

            SUM(
                CASE
                    WHEN status = 'COMPLETED'
                    THEN 1
                    ELSE 0
                END
            ) AS completed_jobs,

            SUM(
                CASE
                    WHEN status = 'CANCELLED'
                    THEN 1
                    ELSE 0
                END
            ) AS cancelled_jobs,

            SUM(
                CASE
                    WHEN status NOT IN (
                        'COMPLETED',
                        'CANCELLED'
                    )
                    THEN 1
                    ELSE 0
                END
            ) AS active_jobs

        FROM service_matches

        WHERE provider_id = ?
        """,
        (provider_id,),
    )

    if not row:
        return {
            "total_jobs": 0,
            "completed_jobs": 0,
            "cancelled_jobs": 0,
            "active_jobs": 0,
        }

    return {
        "total_jobs": row["total_jobs"] or 0,
        "completed_jobs": row["completed_jobs"] or 0,
        "cancelled_jobs": row["cancelled_jobs"] or 0,
        "active_jobs": row["active_jobs"] or 0,
    }


# ==========================================================
# TEST
# ==========================================================

def run_tests():

    print("=" * 60)
    print("RSA PROVIDER JOBS TEST")
    print("=" * 60)

    # ------------------------------------------------------
    # Function availability
    # ------------------------------------------------------

    functions = [
        get_job_by_id,
        get_provider_jobs,
        get_active_jobs,
        validate_job_status,
        update_job_status,
        accept_job,
        mark_on_the_way,
        mark_arrived,
        start_job,
        complete_job,
        cancel_job,
        get_job_summary,
    ]

    print(
        "Module import     : PASS"
    )

    print(
        "Functions loaded  :",
        "PASS"
        if all(callable(fn) for fn in functions)
        else "FAIL",
    )

    # ------------------------------------------------------
    # Valid status
    # ------------------------------------------------------

    try:

        status = validate_job_status(
            " accepted "
        )

        print(
            "Valid status      :",
            "PASS"
            if status == "ACCEPTED"
            else "FAIL",
        )

    except Exception:

        print(
            "Valid status      : FAIL"
        )

    # ------------------------------------------------------
    # Invalid status
    # ------------------------------------------------------

    try:

        validate_job_status(
            "INVALID_STATUS"
        )

        print(
            "Invalid status    : FAIL"
        )

    except ValueError:

        print(
            "Invalid status    : PASS"
        )

    # ------------------------------------------------------
    # Missing job
    # ------------------------------------------------------

    missing_job = get_job_by_id(
        999999999
    )

    print(
        "Missing job       :",
        "PASS"
        if missing_job is None
        else "FAIL",
    )

    # ------------------------------------------------------
    # Missing provider jobs
    # ------------------------------------------------------

    provider_jobs = get_provider_jobs(
        999999999
    )

    print(
        "Provider jobs     :",
        "PASS"
        if isinstance(provider_jobs, list)
        else "FAIL",
    )

    # ------------------------------------------------------
    # Active jobs
    # ------------------------------------------------------

    active_jobs = get_active_jobs(
        999999999
    )

    print(
        "Active jobs       :",
        "PASS"
        if isinstance(active_jobs, list)
        else "FAIL",
    )

    # ------------------------------------------------------
    # Summary
    # ------------------------------------------------------

    summary = get_job_summary(
        999999999
    )

    print(
        "Job summary       :",
        "PASS"
        if isinstance(summary, dict)
        and summary["total_jobs"] == 0
        else "FAIL",
    )

    # ------------------------------------------------------
    # Missing job status update
    # ------------------------------------------------------

    update = update_job_status(
        999999999,
        "ACCEPTED",
    )

    print(
        "Status validation  :",
        "PASS"
        if not update["success"]
        else "FAIL",
    )

    # ------------------------------------------------------
    # Final
    # ------------------------------------------------------

    print("=" * 60)
    print("RSA PROVIDER JOBS TEST COMPLETE")
    print("=" * 60)


# ==========================================================
# ENTRY POINT
# ==========================================================

if __name__ == "__main__":
    run_tests()