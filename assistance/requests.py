"""
RSA - Roadside Assistance
Assistance Request Management

Creates, validates, updates, and manages roadside assistance
requests generated from the RSA AI decision system.
"""

from datetime import datetime
import uuid


class AssistanceRequestManager:

    def __init__(self):

        self.requests = {}

        self.valid_statuses = [
            "PENDING",
            "ASSIGNED",
            "ACCEPTED",
            "EN_ROUTE",
            "ARRIVED",
            "IN_PROGRESS",
            "COMPLETED",
            "CANCELLED"
        ]

        self.valid_priorities = [
            "EMERGENCY",
            "URGENT",
            "NORMAL",
            "LOW"
        ]

    # =============================================================
    # REQUEST ID
    # =============================================================

    def generate_request_id(self):

        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        unique_part = uuid.uuid4().hex[:6].upper()

        return f"RSA-{timestamp}-{unique_part}"

    # =============================================================
    # VALIDATE PRIORITY
    # =============================================================

    def validate_priority(self, priority):

        if not isinstance(priority, str):
            return "LOW"

        priority = priority.strip().upper()

        if priority not in self.valid_priorities:
            return "LOW"

        return priority

    # =============================================================
    # VALIDATE STATUS
    # =============================================================

    def validate_status(self, status):

        if not isinstance(status, str):
            return "PENDING"

        status = status.strip().upper()

        if status not in self.valid_statuses:
            return "PENDING"

        return status

    # =============================================================
    # CREATE REQUEST
    # =============================================================

    def create_request(
        self,
        problem="unknown",
        severity="LOW",
        priority="LOW",
        service="general_roadside_assistance",
        safe_to_drive=True,
        user_id=None,
        location=None,
        description=""
    ):

        if not isinstance(problem, str) or not problem.strip():
            problem = "unknown"
        else:
            problem = problem.strip().lower()

        if not isinstance(severity, str):
            severity = "LOW"
        else:
            severity = severity.strip().upper()

        if severity not in [
            "CRITICAL",
            "HIGH",
            "MEDIUM",
            "LOW"
        ]:
            severity = "LOW"

        priority = self.validate_priority(priority)

        if not isinstance(service, str) or not service.strip():
            service = "general_roadside_assistance"
        else:
            service = service.strip().lower()

        safe_to_drive = bool(safe_to_drive)

        request_id = self.generate_request_id()

        request = {
            "request_id": request_id,

            "user_id": user_id,

            "problem": problem,

            "severity": severity,

            "priority": priority,

            "service": service,

            "safe_to_drive": safe_to_drive,

            "description": description
            if isinstance(description, str)
            else "",

            "location": location,

            "status": "PENDING",

            "provider_id": None,

            "provider_name": None,

            "created_at": datetime.now().isoformat(),

            "updated_at": datetime.now().isoformat(),

            "completed_at": None,

            "cancelled_at": None
        }

        self.requests[request_id] = request

        return request

    # =============================================================
    # GET REQUEST
    # =============================================================

    def get_request(self, request_id):

        if not request_id:
            return None

        return self.requests.get(request_id)

    # =============================================================
    # GET ALL REQUESTS
    # =============================================================

    def get_all_requests(self):

        return list(self.requests.values())

    # =============================================================
    # GET REQUESTS BY USER
    # =============================================================

    def get_user_requests(self, user_id):

        return [
            request
            for request in self.requests.values()
            if request["user_id"] == user_id
        ]

    # =============================================================
    # GET REQUESTS BY STATUS
    # =============================================================

    def get_requests_by_status(self, status):

        status = self.validate_status(status)

        return [
            request
            for request in self.requests.values()
            if request["status"] == status
        ]

    # =============================================================
    # GET REQUESTS BY PRIORITY
    # =============================================================

    def get_requests_by_priority(self, priority):

        priority = self.validate_priority(priority)

        return [
            request
            for request in self.requests.values()
            if request["priority"] == priority
        ]

    # =============================================================
    # UPDATE STATUS
    # =============================================================

    def update_status(self, request_id, status):

        request = self.get_request(request_id)

        if request is None:
            return None

        status = self.validate_status(status)

        request["status"] = status

        request["updated_at"] = datetime.now().isoformat()

        if status == "COMPLETED":

            request["completed_at"] = datetime.now().isoformat()

        if status == "CANCELLED":

            request["cancelled_at"] = datetime.now().isoformat()

        return request

    # =============================================================
    # ASSIGN PROVIDER
    # =============================================================

    def assign_provider(
        self,
        request_id,
        provider_id,
        provider_name=None
    ):

        request = self.get_request(request_id)

        if request is None:
            return None

        if not provider_id:
            return None

        request["provider_id"] = provider_id

        request["provider_name"] = provider_name

        request["status"] = "ASSIGNED"

        request["updated_at"] = datetime.now().isoformat()

        return request

    # =============================================================
    # ACCEPT REQUEST
    # =============================================================

    def accept_request(self, request_id):

        request = self.get_request(request_id)

        if request is None:
            return None

        request["status"] = "ACCEPTED"

        request["updated_at"] = datetime.now().isoformat()

        return request

    # =============================================================
    # MARK EN ROUTE
    # =============================================================

    def mark_en_route(self, request_id):

        request = self.get_request(request_id)

        if request is None:
            return None

        request["status"] = "EN_ROUTE"

        request["updated_at"] = datetime.now().isoformat()

        return request

    # =============================================================
    # MARK ARRIVED
    # =============================================================

    def mark_arrived(self, request_id):

        request = self.get_request(request_id)

        if request is None:
            return None

        request["status"] = "ARRIVED"

        request["updated_at"] = datetime.now().isoformat()

        return request

    # =============================================================
    # START SERVICE
    # =============================================================

    def start_service(self, request_id):

        request = self.get_request(request_id)

        if request is None:
            return None

        request["status"] = "IN_PROGRESS"

        request["updated_at"] = datetime.now().isoformat()

        return request

    # =============================================================
    # COMPLETE REQUEST
    # =============================================================

    def complete_request(self, request_id):

        request = self.get_request(request_id)

        if request is None:
            return None

        request["status"] = "COMPLETED"

        request["completed_at"] = datetime.now().isoformat()

        request["updated_at"] = datetime.now().isoformat()

        return request

    # =============================================================
    # CANCEL REQUEST
    # =============================================================

    def cancel_request(self, request_id):

        request = self.get_request(request_id)

        if request is None:
            return None

        request["status"] = "CANCELLED"

        request["cancelled_at"] = datetime.now().isoformat()

        request["updated_at"] = datetime.now().isoformat()

        return request

    # =============================================================
    # DELETE REQUEST
    # =============================================================

    def delete_request(self, request_id):

        if request_id not in self.requests:
            return False

        del self.requests[request_id]

        return True

    # =============================================================
    # REQUEST SUMMARY
    # =============================================================

    def get_summary(self):

        total = len(self.requests)

        pending = len(
            self.get_requests_by_status("PENDING")
        )

        assigned = len(
            self.get_requests_by_status("ASSIGNED")
        )

        accepted = len(
            self.get_requests_by_status("ACCEPTED")
        )

        en_route = len(
            self.get_requests_by_status("EN_ROUTE")
        )

        arrived = len(
            self.get_requests_by_status("ARRIVED")
        )

        in_progress = len(
            self.get_requests_by_status("IN_PROGRESS")
        )

        completed = len(
            self.get_requests_by_status("COMPLETED")
        )

        cancelled = len(
            self.get_requests_by_status("CANCELLED")
        )

        emergency = len(
            self.get_requests_by_priority("EMERGENCY")
        )

        urgent = len(
            self.get_requests_by_priority("URGENT")
        )

        normal = len(
            self.get_requests_by_priority("NORMAL")
        )

        low = len(
            self.get_requests_by_priority("LOW")
        )

        return {
            "total": total,
            "pending": pending,
            "assigned": assigned,
            "accepted": accepted,
            "en_route": en_route,
            "arrived": arrived,
            "in_progress": in_progress,
            "completed": completed,
            "cancelled": cancelled,
            "emergency": emergency,
            "urgent": urgent,
            "normal": normal,
            "low": low
        }


# =============================================================
# TEST SUITE
# =============================================================

if __name__ == "__main__":

    manager = AssistanceRequestManager()

    print()
    print("=" * 75)
    print("RSA ASSISTANCE REQUEST MANAGER - TEST SUITE")
    print("=" * 75)

    passed_tests = 0
    failed_tests = 0

    # ---------------------------------------------------------
    # TEST 1 - CREATE REQUEST
    # ---------------------------------------------------------

    print()
    print("-" * 75)
    print("TEST              : CREATE REQUEST")

    try:

        request = manager.create_request(
            problem="brake_failure",
            severity="CRITICAL",
            priority="EMERGENCY",
            service="emergency_roadside_assistance",
            safe_to_drive=False,
            user_id="USER001",
            location="Hyderabad",
            description="Brakes have completely failed."
        )

        passed = (
            request is not None
            and request["problem"] == "brake_failure"
            and request["priority"] == "EMERGENCY"
            and request["status"] == "PENDING"
            and request["safe_to_drive"] is False
        )

        if passed:
            passed_tests += 1
            print("STATUS            : PASS")
        else:
            failed_tests += 1
            print("STATUS            : FAIL")

        print(f"Request ID        : {request['request_id']}")
        print(f"Problem           : {request['problem']}")
        print(f"Priority          : {request['priority']}")
        print(f"Service           : {request['service']}")
        print(f"Status            : {request['status']}")

    except Exception as e:

        failed_tests += 1
        print("STATUS            : FAIL")
        print(f"ERROR             : {e}")

    request_id = request["request_id"]

    # ---------------------------------------------------------
    # TEST 2 - GET REQUEST
    # ---------------------------------------------------------

    print()
    print("-" * 75)
    print("TEST              : GET REQUEST")

    try:

        result = manager.get_request(request_id)

        passed = (
            result is not None
            and result["request_id"] == request_id
        )

        if passed:
            passed_tests += 1
            print("STATUS            : PASS")
        else:
            failed_tests += 1
            print("STATUS            : FAIL")

    except Exception as e:

        failed_tests += 1
        print("STATUS            : FAIL")
        print(f"ERROR             : {e}")

    # ---------------------------------------------------------
    # TEST 3 - ASSIGN PROVIDER
    # ---------------------------------------------------------

    print()
    print("-" * 75)
    print("TEST              : ASSIGN PROVIDER")

    try:

        result = manager.assign_provider(
            request_id,
            "PROVIDER001",
            "RSA Emergency Team"
        )

        passed = (
            result is not None
            and result["provider_id"] == "PROVIDER001"
            and result["status"] == "ASSIGNED"
        )

        if passed:
            passed_tests += 1
            print("STATUS            : PASS")
        else:
            failed_tests += 1
            print("STATUS            : FAIL")

    except Exception as e:

        failed_tests += 1
        print("STATUS            : FAIL")
        print(f"ERROR             : {e}")

    # ---------------------------------------------------------
    # TEST 4 - ACCEPT REQUEST
    # ---------------------------------------------------------

    print()
    print("-" * 75)
    print("TEST              : ACCEPT REQUEST")

    try:

        result = manager.accept_request(request_id)

        passed = (
            result is not None
            and result["status"] == "ACCEPTED"
        )

        if passed:
            passed_tests += 1
            print("STATUS            : PASS")
        else:
            failed_tests += 1
            print("STATUS            : FAIL")

    except Exception as e:

        failed_tests += 1
        print("STATUS            : FAIL")
        print(f"ERROR             : {e}")

    # ---------------------------------------------------------
    # TEST 5 - EN ROUTE
    # ---------------------------------------------------------

    print()
    print("-" * 75)
    print("TEST              : EN ROUTE")

    try:

        result = manager.mark_en_route(request_id)

        passed = (
            result is not None
            and result["status"] == "EN_ROUTE"
        )

        if passed:
            passed_tests += 1
            print("STATUS            : PASS")
        else:
            failed_tests += 1
            print("STATUS            : FAIL")

    except Exception as e:

        failed_tests += 1
        print("STATUS            : FAIL")
        print(f"ERROR             : {e}")

    # ---------------------------------------------------------
    # TEST 6 - ARRIVED
    # ---------------------------------------------------------

    print()
    print("-" * 75)
    print("TEST              : ARRIVED")

    try:

        result = manager.mark_arrived(request_id)

        passed = (
            result is not None
            and result["status"] == "ARRIVED"
        )

        if passed:
            passed_tests += 1
            print("STATUS            : PASS")
        else:
            failed_tests += 1
            print("STATUS            : FAIL")

    except Exception as e:

        failed_tests += 1
        print("STATUS            : FAIL")
        print(f"ERROR             : {e}")

    # ---------------------------------------------------------
    # TEST 7 - START SERVICE
    # ---------------------------------------------------------

    print()
    print("-" * 75)
    print("TEST              : START SERVICE")

    try:

        result = manager.start_service(request_id)

        passed = (
            result is not None
            and result["status"] == "IN_PROGRESS"
        )

        if passed:
            passed_tests += 1
            print("STATUS            : PASS")
        else:
            failed_tests += 1
            print("STATUS            : FAIL")

    except Exception as e:

        failed_tests += 1
        print("STATUS            : FAIL")
        print(f"ERROR             : {e}")

    # ---------------------------------------------------------
    # TEST 8 - COMPLETE REQUEST
    # ---------------------------------------------------------

    print()
    print("-" * 75)
    print("TEST              : COMPLETE REQUEST")

    try:

        result = manager.complete_request(request_id)

        passed = (
            result is not None
            and result["status"] == "COMPLETED"
            and result["completed_at"] is not None
        )

        if passed:
            passed_tests += 1
            print("STATUS            : PASS")
        else:
            failed_tests += 1
            print("STATUS            : FAIL")

    except Exception as e:

        failed_tests += 1
        print("STATUS            : FAIL")
        print(f"ERROR             : {e}")

    # ---------------------------------------------------------
    # TEST 9 - SUMMARY
    # ---------------------------------------------------------

    print()
    print("-" * 75)
    print("TEST              : REQUEST SUMMARY")

    try:

        summary = manager.get_summary()

        passed = (
            summary["total"] == 1
            and summary["completed"] == 1
        )

        if passed:
            passed_tests += 1
            print("STATUS            : PASS")
        else:
            failed_tests += 1
            print("STATUS            : FAIL")

        print(f"Total Requests    : {summary['total']}")
        print(f"Completed         : {summary['completed']}")
        print(f"Emergency         : {summary['emergency']}")

    except Exception as e:

        failed_tests += 1
        print("STATUS            : FAIL")
        print(f"ERROR             : {e}")

    # =========================================================
    # FINAL RESULTS
    # =========================================================

    total_tests = passed_tests + failed_tests

    print()
    print("=" * 75)
    print("RSA ASSISTANCE REQUEST MANAGER TEST RESULTS")
    print("=" * 75)

    print(f"TOTAL TESTS       : {total_tests}")
    print(f"PASSED            : {passed_tests}")
    print(f"FAILED            : {failed_tests}")

    print("=" * 75)

    if failed_tests == 0:

        print("ALL TESTS PASSED")
        print(
            "RSA ASSISTANCE REQUEST MANAGER "
            "IS WORKING CORRECTLY"
        )

    else:

        print("SOME TESTS FAILED")

    print("=" * 75)