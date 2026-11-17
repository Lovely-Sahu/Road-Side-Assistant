"""
RSA - Roadside Assistance
Service Matching Engine

Matches an analyzed vehicle incident with the most
appropriate roadside assistance service.
"""


class AssistanceMatcher:

    def __init__(self):

        # ---------------------------------------------------------
        # SERVICE DEFINITIONS
        # ---------------------------------------------------------

        self.services = {

            "emergency_services": {
                "name": "Emergency Services",
                "priority": "EMERGENCY",
                "description": (
                    "Immediate emergency response for accidents, "
                    "injuries, fire, or other dangerous situations."
                )
            },

            "emergency_roadside_assistance": {
                "name": "Emergency Roadside Assistance",
                "priority": "EMERGENCY",
                "description": (
                    "Immediate roadside support for dangerous "
                    "vehicle failures."
                )
            },

            "mechanic_or_roadside_assistance": {
                "name": "Mechanic / Roadside Assistance",
                "priority": "URGENT",
                "description": (
                    "Mechanical assistance for engine and major "
                    "vehicle failures."
                )
            },

            "tyre_assistance": {
                "name": "Tyre Assistance",
                "priority": "URGENT",
                "description": (
                    "Tyre repair or replacement assistance."
                )
            },

            "battery_assistance": {
                "name": "Battery Assistance",
                "priority": "NORMAL",
                "description": (
                    "Battery jump-start, battery inspection, "
                    "or battery replacement."
                )
            },

            "fuel_delivery": {
                "name": "Fuel Delivery",
                "priority": "NORMAL",
                "description": (
                    "Fuel delivery for vehicles that have "
                    "run out of fuel."
                )
            },

            "electrical_vehicle_assistance": {
                "name": "Electrical Vehicle Assistance",
                "priority": "NORMAL",
                "description": (
                    "Electrical system inspection and repair."
                )
            },

            "general_roadside_assistance": {
                "name": "General Roadside Assistance",
                "priority": "LOW",
                "description": (
                    "General vehicle diagnosis and roadside support."
                )
            }
        }

        # ---------------------------------------------------------
        # PROBLEM → SERVICE MAPPING
        # ---------------------------------------------------------

        self.problem_service_map = {

            "brake_failure":
                "emergency_roadside_assistance",

            "accident":
                "emergency_services",

            "engine_overheating":
                "mechanic_or_roadside_assistance",

            "engine_failure":
                "mechanic_or_roadside_assistance",

            "tyre_puncture":
                "tyre_assistance",

            "battery_failure":
                "battery_assistance",

            "fuel_problem":
                "fuel_delivery",

            "electrical_failure":
                "electrical_vehicle_assistance",

            "unknown":
                "general_roadside_assistance"
        }

        # ---------------------------------------------------------
        # PRIORITY ORDER
        # ---------------------------------------------------------

        self.priority_order = {
            "EMERGENCY": 4,
            "URGENT": 3,
            "NORMAL": 2,
            "LOW": 1
        }

    # =============================================================
    # VALIDATE INPUT
    # =============================================================

    def _validate_input(self, problem, severity, safe_to_drive):

        if not isinstance(problem, str):
            problem = "unknown"

        problem = problem.strip().lower()

        if not problem:
            problem = "unknown"

        if not isinstance(severity, str):
            severity = "LOW"

        severity = severity.strip().upper()

        if severity not in [
            "CRITICAL",
            "HIGH",
            "MEDIUM",
            "LOW"
        ]:
            severity = "LOW"

        safe_to_drive = bool(safe_to_drive)

        return problem, severity, safe_to_drive

    # =============================================================
    # GET SERVICE
    # =============================================================

    def get_service_for_problem(self, problem):

        if not isinstance(problem, str):
            problem = "unknown"

        problem = problem.strip().lower()

        return self.problem_service_map.get(
            problem,
            "general_roadside_assistance"
        )

    # =============================================================
    # DETERMINE PRIORITY
    # =============================================================

    def determine_priority(
        self,
        problem,
        severity,
        safe_to_drive
    ):

        problem, severity, safe_to_drive = self._validate_input(
            problem,
            severity,
            safe_to_drive
        )

        # ---------------------------------------------------------
        # Emergency problems
        # ---------------------------------------------------------

        if problem in [
            "brake_failure",
            "accident"
        ]:
            return "EMERGENCY"

        # ---------------------------------------------------------
        # Critical severity
        # ---------------------------------------------------------

        if severity == "CRITICAL":
            return "EMERGENCY"

        # ---------------------------------------------------------
        # Unsafe vehicle
        # ---------------------------------------------------------

        if not safe_to_drive:

            if severity == "HIGH":
                return "URGENT"

            if problem in [
                "engine_overheating",
                "engine_failure",
                "tyre_puncture"
            ]:
                return "URGENT"

        # ---------------------------------------------------------
        # High severity
        # ---------------------------------------------------------

        if severity == "HIGH":
            return "URGENT"

        # ---------------------------------------------------------
        # Medium severity
        # ---------------------------------------------------------

        if severity == "MEDIUM":
            return "NORMAL"

        # ---------------------------------------------------------
        # Low severity
        # ---------------------------------------------------------

        return "LOW"

    # =============================================================
    # DETERMINE SERVICE
    # =============================================================

    def determine_service(
        self,
        problem,
        severity,
        safe_to_drive
    ):

        problem, severity, safe_to_drive = self._validate_input(
            problem,
            severity,
            safe_to_drive
        )

        service = self.get_service_for_problem(problem)

        # ---------------------------------------------------------
        # Safety overrides
        # ---------------------------------------------------------

        if problem == "brake_failure":
            return "emergency_roadside_assistance"

        if problem == "accident":
            return "emergency_services"

        # ---------------------------------------------------------
        # Engine problems
        # ---------------------------------------------------------

        if problem in [
            "engine_overheating",
            "engine_failure"
        ]:
            return "mechanic_or_roadside_assistance"

        # ---------------------------------------------------------
        # Tyre
        # ---------------------------------------------------------

        if problem == "tyre_puncture":
            return "tyre_assistance"

        # ---------------------------------------------------------
        # Battery
        # ---------------------------------------------------------

        if problem == "battery_failure":
            return "battery_assistance"

        # ---------------------------------------------------------
        # Fuel
        # ---------------------------------------------------------

        if problem == "fuel_problem":
            return "fuel_delivery"

        # ---------------------------------------------------------
        # Electrical
        # ---------------------------------------------------------

        if problem == "electrical_failure":
            return "electrical_vehicle_assistance"

        return service

    # =============================================================
    # MATCH ASSISTANCE
    # =============================================================

    def match_assistance(
        self,
        problem,
        severity,
        safe_to_drive
    ):

        problem, severity, safe_to_drive = self._validate_input(
            problem,
            severity,
            safe_to_drive
        )

        priority = self.determine_priority(
            problem,
            severity,
            safe_to_drive
        )

        service_id = self.determine_service(
            problem,
            severity,
            safe_to_drive
        )

        service = self.services.get(
            service_id,
            self.services["general_roadside_assistance"]
        )

        escalation_required = (
            priority == "EMERGENCY"
            or not safe_to_drive
        )

        return {
            "problem": problem,
            "severity": severity,
            "safe_to_drive": safe_to_drive,
            "priority": priority,
            "service": service_id,
            "service_name": service["name"],
            "service_description": service["description"],
            "escalation_required": escalation_required
        }

    # =============================================================
    # GET AVAILABLE SERVICES
    # =============================================================

    def get_available_services(self):

        return self.services.copy()

    # =============================================================
    # GET SERVICE DETAILS
    # =============================================================

    def get_service_details(self, service_id):

        if service_id not in self.services:

            service_id = "general_roadside_assistance"

        service = self.services[service_id]

        return {
            "service": service_id,
            "name": service["name"],
            "priority": service["priority"],
            "description": service["description"]
        }


# =============================================================
# TEST SUITE
# =============================================================

if __name__ == "__main__":

    matcher = AssistanceMatcher()

    test_cases = [

        (
            "BRAKE FAILURE",
            "brake_failure",
            "CRITICAL",
            False,
            "EMERGENCY",
            "emergency_roadside_assistance"
        ),

        (
            "ACCIDENT",
            "accident",
            "CRITICAL",
            False,
            "EMERGENCY",
            "emergency_services"
        ),

        (
            "ENGINE OVERHEATING",
            "engine_overheating",
            "CRITICAL",
            False,
            "EMERGENCY",
            "mechanic_or_roadside_assistance"
        ),

        (
            "ENGINE FAILURE",
            "engine_failure",
            "HIGH",
            False,
            "URGENT",
            "mechanic_or_roadside_assistance"
        ),

        (
            "TYRE PUNCTURE",
            "tyre_puncture",
            "HIGH",
            False,
            "URGENT",
            "tyre_assistance"
        ),

        (
            "BATTERY FAILURE",
            "battery_failure",
            "MEDIUM",
            True,
            "NORMAL",
            "battery_assistance"
        ),

        (
            "FUEL PROBLEM",
            "fuel_problem",
            "MEDIUM",
            True,
            "NORMAL",
            "fuel_delivery"
        ),

        (
            "ELECTRICAL FAILURE",
            "electrical_failure",
            "MEDIUM",
            True,
            "NORMAL",
            "electrical_vehicle_assistance"
        ),

        (
            "UNKNOWN",
            "unknown",
            "LOW",
            True,
            "LOW",
            "general_roadside_assistance"
        )
    ]

    print()
    print("=" * 75)
    print("RSA ASSISTANCE MATCHING ENGINE - TEST SUITE")
    print("=" * 75)

    passed_tests = 0
    failed_tests = 0

    for (
        test_name,
        problem,
        severity,
        safe_to_drive,
        expected_priority,
        expected_service
    ) in test_cases:

        print()
        print("-" * 75)
        print(f"TEST              : {test_name}")
        print(f"Expected Priority : {expected_priority}")
        print(f"Expected Service  : {expected_service}")

        try:

            result = matcher.match_assistance(
                problem,
                severity,
                safe_to_drive
            )

            actual_priority = result["priority"]
            actual_service = result["service"]

            passed = (
                actual_priority == expected_priority
                and actual_service == expected_service
            )

            if passed:
                passed_tests += 1
                status = "PASS"
            else:
                failed_tests += 1
                status = "FAIL"

            print(f"STATUS            : {status}")
            print(f"Actual Priority   : {actual_priority}")
            print(f"Actual Service    : {actual_service}")
            print(
                f"Escalation        : "
                f"{result['escalation_required']}"
            )
            print(
                f"Safe To Drive     : "
                f"{result['safe_to_drive']}"
            )
            print(
                f"Service Name      : "
                f"{result['service_name']}"
            )
            print(
                f"Description       : "
                f"{result['service_description']}"
            )

        except Exception as e:

            failed_tests += 1

            print("STATUS            : FAIL")
            print(f"ERROR             : {e}")

    print()
    print("=" * 75)
    print("RSA ASSISTANCE MATCHING ENGINE TEST RESULTS")
    print("=" * 75)

    total_tests = len(test_cases)

    print(f"TOTAL TESTS       : {total_tests}")
    print(f"PASSED            : {passed_tests}")
    print(f"FAILED            : {failed_tests}")

    print("=" * 75)

    if failed_tests == 0:

        print("ALL TESTS PASSED")
        print("RSA ASSISTANCE MATCHING ENGINE IS WORKING CORRECTLY")

    else:

        print("SOME TESTS FAILED")

    print("=" * 75)