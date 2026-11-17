"""
RSA - ASSISTANCE TRACKING ENGINE

Tracks roadside assistance requests from creation to completion.

Status flow:
REQUESTED -> ASSIGNED -> EN_ROUTE -> ARRIVED -> IN_PROGRESS -> COMPLETED

The engine also supports:
- technician/provider assignment
- ETA tracking
- status updates
- location updates
- tracking history
- request cancellation
- completion
- test suite
"""


from datetime import datetime, timedelta


class TrackingEngine:
    """
    Roadside Assistance Tracking Engine
    """

    VALID_STATUSES = [
        "REQUESTED",
        "ASSIGNED",
        "EN_ROUTE",
        "ARRIVED",
        "IN_PROGRESS",
        "COMPLETED",
        "CANCELLED",
    ]

    ALLOWED_TRANSITIONS = {
        "REQUESTED": ["ASSIGNED", "CANCELLED"],
        "ASSIGNED": ["EN_ROUTE", "CANCELLED"],
        "EN_ROUTE": ["ARRIVED", "CANCELLED"],
        "ARRIVED": ["IN_PROGRESS", "CANCELLED"],
        "IN_PROGRESS": ["COMPLETED", "CANCELLED"],
        "COMPLETED": [],
        "CANCELLED": [],
    }

    def __init__(self):
        self.tracking_records = {}
        self.next_tracking_id = 1

    # ------------------------------------------------------------------
    # INTERNAL HELPERS
    # ------------------------------------------------------------------

    def _timestamp(self):
        """Return current timestamp as a readable string."""
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def _generate_tracking_id(self):
        """Generate unique tracking ID."""
        tracking_id = f"TRK{self.next_tracking_id:05d}"
        self.next_tracking_id += 1
        return tracking_id

    def _get_record(self, tracking_id):
        """Return tracking record or None."""
        return self.tracking_records.get(tracking_id)

    # ------------------------------------------------------------------
    # CREATE TRACKING
    # ------------------------------------------------------------------

    def create_tracking(
        self,
        request_id,
        problem,
        service,
        priority="NORMAL",
        safe_to_drive=True,
    ):
        """
        Create a new assistance tracking record.
        """

        if not request_id:
            return {
                "success": False,
                "message": "Request ID is required.",
            }

        tracking_id = self._generate_tracking_id()

        record = {
            "tracking_id": tracking_id,
            "request_id": request_id,
            "problem": problem,
            "service": service,
            "priority": priority,
            "safe_to_drive": safe_to_drive,
            "status": "REQUESTED",
            "provider": None,
            "technician": None,
            "vehicle_location": None,
            "technician_location": None,
            "eta_minutes": None,
            "created_at": self._timestamp(),
            "updated_at": self._timestamp(),
            "completed_at": None,
            "cancelled_at": None,
            "history": [
                {
                    "status": "REQUESTED",
                    "message": "Assistance request created.",
                    "timestamp": self._timestamp(),
                }
            ],
        }

        self.tracking_records[tracking_id] = record

        return {
            "success": True,
            "tracking_id": tracking_id,
            "status": "REQUESTED",
            "message": "Assistance request is now being tracked.",
            "record": record,
        }

    # ------------------------------------------------------------------
    # ASSIGN PROVIDER
    # ------------------------------------------------------------------

    def assign_provider(
        self,
        tracking_id,
        provider,
        technician=None,
        eta_minutes=None,
    ):
        """
        Assign a roadside assistance provider/technician.
        """

        record = self._get_record(tracking_id)

        if not record:
            return {
                "success": False,
                "message": "Tracking record not found.",
            }

        if record["status"] != "REQUESTED":
            return {
                "success": False,
                "message": (
                    f"Provider can only be assigned when status is REQUESTED. "
                    f"Current status: {record['status']}"
                ),
            }

        record["provider"] = provider
        record["technician"] = technician
        record["eta_minutes"] = eta_minutes

        self._update_status(
            record,
            "ASSIGNED",
            "Assistance provider assigned.",
        )

        return {
            "success": True,
            "tracking_id": tracking_id,
            "status": record["status"],
            "provider": provider,
            "technician": technician,
            "eta_minutes": eta_minutes,
            "message": "Assistance provider assigned successfully.",
        }

    # ------------------------------------------------------------------
    # STATUS UPDATE
    # ------------------------------------------------------------------

    def update_status(self, tracking_id, new_status, message=None):
        """
        Update assistance tracking status.
        """

        record = self._get_record(tracking_id)

        if not record:
            return {
                "success": False,
                "message": "Tracking record not found.",
            }

        new_status = str(new_status).upper().strip()

        if new_status not in self.VALID_STATUSES:
            return {
                "success": False,
                "message": f"Invalid status: {new_status}",
            }

        current_status = record["status"]

        if new_status == current_status:
            return {
                "success": False,
                "message": f"Tracking is already {current_status}.",
            }

        allowed = self.ALLOWED_TRANSITIONS.get(current_status, [])

        if new_status not in allowed:
            return {
                "success": False,
                "message": (
                    f"Invalid status transition: "
                    f"{current_status} -> {new_status}"
                ),
            }

        default_messages = {
            "ASSIGNED": "Assistance provider assigned.",
            "EN_ROUTE": "Assistance provider is on the way.",
            "ARRIVED": "Assistance provider has arrived.",
            "IN_PROGRESS": "Assistance service is in progress.",
            "COMPLETED": "Assistance service completed successfully.",
            "CANCELLED": "Assistance request cancelled.",
        }

        if not message:
            message = default_messages.get(
                new_status,
                f"Status changed to {new_status}.",
            )

        self._update_status(record, new_status, message)

        return {
            "success": True,
            "tracking_id": tracking_id,
            "status": new_status,
            "message": message,
            "updated_at": record["updated_at"],
        }

    # ------------------------------------------------------------------
    # INTERNAL STATUS UPDATE
    # ------------------------------------------------------------------

    def _update_status(self, record, new_status, message):
        """Internal status update helper."""

        now = self._timestamp()

        record["status"] = new_status
        record["updated_at"] = now

        if new_status == "COMPLETED":
            record["completed_at"] = now

        if new_status == "CANCELLED":
            record["cancelled_at"] = now

        record["history"].append(
            {
                "status": new_status,
                "message": message,
                "timestamp": now,
            }
        )

    # ------------------------------------------------------------------
    # LOCATION UPDATE
    # ------------------------------------------------------------------

    def update_vehicle_location(
        self,
        tracking_id,
        latitude,
        longitude,
    ):
        """
        Update customer's vehicle location.
        """

        record = self._get_record(tracking_id)

        if not record:
            return {
                "success": False,
                "message": "Tracking record not found.",
            }

        record["vehicle_location"] = {
            "latitude": latitude,
            "longitude": longitude,
            "updated_at": self._timestamp(),
        }

        record["updated_at"] = self._timestamp()

        return {
            "success": True,
            "tracking_id": tracking_id,
            "vehicle_location": record["vehicle_location"],
            "message": "Vehicle location updated successfully.",
        }

    # ------------------------------------------------------------------
    # TECHNICIAN LOCATION
    # ------------------------------------------------------------------

    def update_technician_location(
        self,
        tracking_id,
        latitude,
        longitude,
    ):
        """
        Update assistance provider location.
        """

        record = self._get_record(tracking_id)

        if not record:
            return {
                "success": False,
                "message": "Tracking record not found.",
            }

        record["technician_location"] = {
            "latitude": latitude,
            "longitude": longitude,
            "updated_at": self._timestamp(),
        }

        record["updated_at"] = self._timestamp()

        return {
            "success": True,
            "tracking_id": tracking_id,
            "technician_location": record["technician_location"],
            "message": "Technician location updated successfully.",
        }

    # ------------------------------------------------------------------
    # ETA UPDATE
    # ------------------------------------------------------------------

    def update_eta(self, tracking_id, eta_minutes):
        """
        Update estimated arrival time.
        """

        record = self._get_record(tracking_id)

        if not record:
            return {
                "success": False,
                "message": "Tracking record not found.",
            }

        try:
            eta_minutes = int(eta_minutes)

            if eta_minutes < 0:
                raise ValueError

        except (ValueError, TypeError):
            return {
                "success": False,
                "message": "ETA must be a non-negative number of minutes.",
            }

        record["eta_minutes"] = eta_minutes
        record["updated_at"] = self._timestamp()

        return {
            "success": True,
            "tracking_id": tracking_id,
            "eta_minutes": eta_minutes,
            "message": "ETA updated successfully.",
        }

    # ------------------------------------------------------------------
    # GET TRACKING
    # ------------------------------------------------------------------

    def get_tracking(self, tracking_id):
        """
        Return current tracking information.
        """

        record = self._get_record(tracking_id)

        if not record:
            return {
                "success": False,
                "message": "Tracking record not found.",
            }

        return {
            "success": True,
            "tracking": record,
        }

    # ------------------------------------------------------------------
    # TRACKING SUMMARY
    # ------------------------------------------------------------------

    def get_summary(self, tracking_id):
        """
        Return a simplified tracking summary.
        """

        record = self._get_record(tracking_id)

        if not record:
            return {
                "success": False,
                "message": "Tracking record not found.",
            }

        return {
            "success": True,
            "tracking_id": record["tracking_id"],
            "request_id": record["request_id"],
            "problem": record["problem"],
            "service": record["service"],
            "priority": record["priority"],
            "status": record["status"],
            "provider": record["provider"],
            "technician": record["technician"],
            "eta_minutes": record["eta_minutes"],
            "safe_to_drive": record["safe_to_drive"],
            "vehicle_location": record["vehicle_location"],
            "technician_location": record["technician_location"],
            "created_at": record["created_at"],
            "updated_at": record["updated_at"],
        }

    # ------------------------------------------------------------------
    # HISTORY
    # ------------------------------------------------------------------

    def get_history(self, tracking_id):
        """
        Return complete status history.
        """

        record = self._get_record(tracking_id)

        if not record:
            return {
                "success": False,
                "message": "Tracking record not found.",
            }

        return {
            "success": True,
            "tracking_id": tracking_id,
            "history": record["history"],
        }

    # ------------------------------------------------------------------
    # CANCEL REQUEST
    # ------------------------------------------------------------------

    def cancel_tracking(self, tracking_id, reason="User cancelled request."):
        """
        Cancel an active assistance request.
        """

        record = self._get_record(tracking_id)

        if not record:
            return {
                "success": False,
                "message": "Tracking record not found.",
            }

        if record["status"] in ["COMPLETED", "CANCELLED"]:
            return {
                "success": False,
                "message": (
                    f"Request cannot be cancelled because it is "
                    f"already {record['status']}."
                ),
            }

        result = self.update_status(
            tracking_id,
            "CANCELLED",
            reason,
        )

        return result

    # ------------------------------------------------------------------
    # COMPLETE REQUEST
    # ------------------------------------------------------------------

    def complete_tracking(
        self,
        tracking_id,
        completion_message="Assistance service completed successfully.",
    ):
        """
        Mark assistance request as completed.

        The request must first be in IN_PROGRESS state.
        """

        record = self._get_record(tracking_id)

        if not record:
            return {
                "success": False,
                "message": "Tracking record not found.",
            }

        if record["status"] != "IN_PROGRESS":
            return {
                "success": False,
                "message": (
                    "Request can only be completed when assistance "
                    "is IN_PROGRESS."
                ),
            }

        return self.update_status(
            tracking_id,
            "COMPLETED",
            completion_message,
        )

    # ------------------------------------------------------------------
    # ACTIVE REQUESTS
    # ------------------------------------------------------------------

    def get_active_requests(self):
        """
        Return all currently active tracking records.
        """

        active_statuses = [
            "REQUESTED",
            "ASSIGNED",
            "EN_ROUTE",
            "ARRIVED",
            "IN_PROGRESS",
        ]

        active = []

        for record in self.tracking_records.values():
            if record["status"] in active_statuses:
                active.append(record)

        return {
            "success": True,
            "count": len(active),
            "requests": active,
        }

    # ------------------------------------------------------------------
    # ALL REQUESTS
    # ------------------------------------------------------------------

    def get_all_requests(self):
        """
        Return all tracking records.
        """

        records = list(self.tracking_records.values())

        return {
            "success": True,
            "count": len(records),
            "requests": records,
        }


# ==========================================================================
# TEST SUITE
# ==========================================================================


def run_tests():

    print("=" * 75)
    print("RSA ASSISTANCE TRACKING ENGINE - TEST SUITE")
    print("=" * 75)

    engine = TrackingEngine()

    total_tests = 0
    passed_tests = 0
    failed_tests = 0

    # ------------------------------------------------------------------
    # TEST 1 - CREATE REQUEST
    # ------------------------------------------------------------------

    print("\n" + "-" * 75)
    print("TEST              : CREATE TRACKING REQUEST")

    total_tests += 1

    result = engine.create_tracking(
        request_id="REQ001",
        problem="brake_failure",
        service="emergency_roadside_assistance",
        priority="EMERGENCY",
        safe_to_drive=False,
    )

    tracking_id = result.get("tracking_id")

    expected_status = "REQUESTED"
    actual_status = result.get("status")

    if result["success"] and actual_status == expected_status:
        print("STATUS            : PASS")
        passed_tests += 1
    else:
        print("STATUS            : FAIL")
        failed_tests += 1

    print(f"Tracking ID       : {tracking_id}")
    print(f"Expected Status   : {expected_status}")
    print(f"Actual Status     : {actual_status}")

    # ------------------------------------------------------------------
    # TEST 2 - ASSIGN PROVIDER
    # ------------------------------------------------------------------

    print("\n" + "-" * 75)
    print("TEST              : PROVIDER ASSIGNMENT")

    total_tests += 1

    result = engine.assign_provider(
        tracking_id,
        provider="RSA Emergency Assistance",
        technician="Technician 001",
        eta_minutes=20,
    )

    if (
        result["success"]
        and result["status"] == "ASSIGNED"
        and result["provider"] == "RSA Emergency Assistance"
    ):
        print("STATUS            : PASS")
        passed_tests += 1
    else:
        print("STATUS            : FAIL")
        failed_tests += 1

    print(f"Actual Status     : {result.get('status')}")
    print(f"Provider          : {result.get('provider')}")
    print(f"Technician        : {result.get('technician')}")
    print(f"ETA               : {result.get('eta_minutes')} minutes")

    # ------------------------------------------------------------------
    # TEST 3 - EN ROUTE
    # ------------------------------------------------------------------

    print("\n" + "-" * 75)
    print("TEST              : PROVIDER EN ROUTE")

    total_tests += 1

    result = engine.update_status(
        tracking_id,
        "EN_ROUTE",
    )

    if result["success"] and result["status"] == "EN_ROUTE":
        print("STATUS            : PASS")
        passed_tests += 1
    else:
        print("STATUS            : FAIL")
        failed_tests += 1

    print(f"Actual Status     : {result.get('status')}")
    print(f"Message           : {result.get('message')}")

    # ------------------------------------------------------------------
    # TEST 4 - LOCATION UPDATE
    # ------------------------------------------------------------------

    print("\n" + "-" * 75)
    print("TEST              : VEHICLE LOCATION UPDATE")

    total_tests += 1

    result = engine.update_vehicle_location(
        tracking_id,
        17.3850,
        78.4867,
    )

    if result["success"]:
        print("STATUS            : PASS")
        passed_tests += 1
    else:
        print("STATUS            : FAIL")
        failed_tests += 1

    print(f"Location          : {result.get('vehicle_location')}")

    # ------------------------------------------------------------------
    # TEST 5 - TECHNICIAN LOCATION
    # ------------------------------------------------------------------

    print("\n" + "-" * 75)
    print("TEST              : TECHNICIAN LOCATION UPDATE")

    total_tests += 1

    result = engine.update_technician_location(
        tracking_id,
        17.3900,
        78.4900,
    )

    if result["success"]:
        print("STATUS            : PASS")
        passed_tests += 1
    else:
        print("STATUS            : FAIL")
        failed_tests += 1

    print(f"Location          : {result.get('technician_location')}")

    # ------------------------------------------------------------------
    # TEST 6 - ARRIVED
    # ------------------------------------------------------------------

    print("\n" + "-" * 75)
    print("TEST              : PROVIDER ARRIVAL")

    total_tests += 1

    result = engine.update_status(
        tracking_id,
        "ARRIVED",
    )

    if result["success"] and result["status"] == "ARRIVED":
        print("STATUS            : PASS")
        passed_tests += 1
    else:
        print("STATUS            : FAIL")
        failed_tests += 1

    print(f"Actual Status     : {result.get('status')}")

    # ------------------------------------------------------------------
    # TEST 7 - SERVICE IN PROGRESS
    # ------------------------------------------------------------------

    print("\n" + "-" * 75)
    print("TEST              : SERVICE IN PROGRESS")

    total_tests += 1

    result = engine.update_status(
        tracking_id,
        "IN_PROGRESS",
    )

    if result["success"] and result["status"] == "IN_PROGRESS":
        print("STATUS            : PASS")
        passed_tests += 1
    else:
        print("STATUS            : FAIL")
        failed_tests += 1

    print(f"Actual Status     : {result.get('status')}")

    # ------------------------------------------------------------------
    # TEST 8 - COMPLETE
    # ------------------------------------------------------------------

    print("\n" + "-" * 75)
    print("TEST              : COMPLETE ASSISTANCE")

    total_tests += 1

    result = engine.complete_tracking(
        tracking_id,
    )

    if result["success"] and result["status"] == "COMPLETED":
        print("STATUS            : PASS")
        passed_tests += 1
    else:
        print("STATUS            : FAIL")
        failed_tests += 1

    print(f"Actual Status     : {result.get('status')}")
    print(f"Message           : {result.get('message')}")

    # ------------------------------------------------------------------
    # TEST 9 - HISTORY
    # ------------------------------------------------------------------

    print("\n" + "-" * 75)
    print("TEST              : TRACKING HISTORY")

    total_tests += 1

    result = engine.get_history(tracking_id)

    history = result.get("history", [])

    expected_history = [
        "REQUESTED",
        "ASSIGNED",
        "EN_ROUTE",
        "ARRIVED",
        "IN_PROGRESS",
        "COMPLETED",
    ]

    actual_history = [
        item["status"]
        for item in history
    ]

    if result["success"] and actual_history == expected_history:
        print("STATUS            : PASS")
        passed_tests += 1
    else:
        print("STATUS            : FAIL")
        failed_tests += 1

    print(f"Expected History  : {expected_history}")
    print(f"Actual History    : {actual_history}")

    # ------------------------------------------------------------------
    # RESULTS
    # ------------------------------------------------------------------

    print("\n" + "=" * 75)
    print("RSA ASSISTANCE TRACKING ENGINE TEST RESULTS")
    print("=" * 75)

    print(f"TOTAL TESTS       : {total_tests}")
    print(f"PASSED            : {passed_tests}")
    print(f"FAILED            : {failed_tests}")

    print("=" * 75)

    if failed_tests == 0:
        print("ALL TESTS PASSED")
        print("RSA ASSISTANCE TRACKING ENGINE IS WORKING CORRECTLY")
    else:
        print("SOME TESTS FAILED")

    print("=" * 75)


# ==========================================================================
# RUN TESTS
# ==========================================================================

if __name__ == "__main__":
    run_tests()