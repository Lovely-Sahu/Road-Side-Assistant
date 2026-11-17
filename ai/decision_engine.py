# ============================================================
# RSA - AI DECISION ENGINE
# ============================================================

class DecisionEngine:

    # ---------------------------------------------------------
    # INITIALIZATION
    # ---------------------------------------------------------

    def __init__(self):

        # Priority levels
        self.priority_levels = {
            "EMERGENCY": 4,
            "URGENT": 3,
            "NORMAL": 2,
            "LOW": 1
        }

        # Default service mapping
        self.service_mapping = {

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
    # DETERMINE PRIORITY
    # ---------------------------------------------------------

    def determine_priority(
        self,
        problem,
        severity,
        safe_to_drive
    ):

        # -----------------------------------------------------
        # EMERGENCY CONDITIONS
        # -----------------------------------------------------

        if problem in [
            "brake_failure",
            "accident"
        ]:

            return "EMERGENCY"

        if problem == "engine_overheating":

            return "EMERGENCY"

        if severity == "CRITICAL":

            return "EMERGENCY"

        # -----------------------------------------------------
        # URGENT CONDITIONS
        # -----------------------------------------------------

        if problem in [
            "engine_failure",
            "tyre_puncture"
        ]:

            return "URGENT"

        if severity == "HIGH":

            return "URGENT"

        # -----------------------------------------------------
        # NORMAL CONDITIONS
        # -----------------------------------------------------

        if problem in [
            "battery_failure",
            "fuel_problem",
            "electrical_failure"
        ]:

            return "NORMAL"

        if severity == "MEDIUM":

            return "NORMAL"

        # -----------------------------------------------------
        # LOW RISK
        # -----------------------------------------------------

        return "LOW"

    # ---------------------------------------------------------
    # DETERMINE SERVICE
    # ---------------------------------------------------------

    def determine_service(self, problem):

        return self.service_mapping.get(
            problem,
            "general_roadside_assistance"
        )

    # ---------------------------------------------------------
    # DETERMINE ESCALATION
    # ---------------------------------------------------------

    def determine_escalation(self, priority):

        # IMPORTANT:
        # Only EMERGENCY cases are escalated.
        #
        # URGENT cases require immediate roadside assistance,
        # but they are NOT classified as emergency escalation.

        if priority == "EMERGENCY":

            return True

        return False

    # ---------------------------------------------------------
    # DECISION MESSAGE
    # ---------------------------------------------------------

    def generate_decision(
        self,
        priority,
        service,
        safe_to_drive
    ):

        if priority == "EMERGENCY":

            return (
                "Emergency assistance is required. "
                f"Recommended service: {service}."
            )

        if priority == "URGENT":

            return (
                "Urgent roadside assistance is recommended. "
                f"Recommended service: {service}."
            )

        if priority == "NORMAL":

            return (
                "Roadside assistance is recommended. "
                f"Recommended service: {service}."
            )

        return (
            "The incident appears to be low risk. "
            f"Recommended service: {service}."
        )

    # ---------------------------------------------------------
    # USER ACTION
    # ---------------------------------------------------------

    def generate_user_action(
        self,
        problem,
        priority,
        safe_to_drive
    ):

        # -----------------------------------------------------
        # BRAKE FAILURE
        # -----------------------------------------------------

        if problem == "brake_failure":

            return (
                "Do not continue driving. "
                "Bring the vehicle to a safe location if possible "
                "and request emergency roadside assistance."
            )

        # -----------------------------------------------------
        # ACCIDENT
        # -----------------------------------------------------

        if problem == "accident":

            return (
                "Move to a safe location if possible, "
                "check for injuries, and contact emergency "
                "services immediately."
            )

        # -----------------------------------------------------
        # ENGINE OVERHEATING
        # -----------------------------------------------------

        if problem == "engine_overheating":

            return (
                "Stop driving when it is safe to do so, "
                "move to a safe location, and request "
                "emergency assistance."
            )

        # -----------------------------------------------------
        # ENGINE FAILURE
        # -----------------------------------------------------

        if problem == "engine_failure":

            return (
                "Do not continue normal driving. "
                "Move to a safe location and request "
                "roadside assistance."
            )

        # -----------------------------------------------------
        # TYRE PUNCTURE
        # -----------------------------------------------------

        if problem == "tyre_puncture":

            return (
                "Do not continue normal driving. "
                "Move to a safe location and request "
                "roadside assistance."
            )

        # -----------------------------------------------------
        # BATTERY FAILURE
        # -----------------------------------------------------

        if problem == "battery_failure":

            return (
                "Arrange roadside assistance or professional "
                "vehicle inspection before continuing normal use."
            )

        # -----------------------------------------------------
        # FUEL PROBLEM
        # -----------------------------------------------------

        if problem == "fuel_problem":

            return (
                "Arrange roadside assistance or professional "
                "vehicle inspection before continuing normal use."
            )

        # -----------------------------------------------------
        # ELECTRICAL FAILURE
        # -----------------------------------------------------

        if problem == "electrical_failure":

            return (
                "Arrange roadside assistance or professional "
                "vehicle inspection before continuing normal use."
            )

        # -----------------------------------------------------
        # UNKNOWN
        # -----------------------------------------------------

        return (
            "Drive carefully and arrange professional diagnosis "
            "if the problem continues."
        )

    # ---------------------------------------------------------
    # COMPLETE DECISION
    # ---------------------------------------------------------

    def make_decision(
        self,
        problem,
        severity,
        safe_to_drive
    ):

        priority = self.determine_priority(
            problem,
            severity,
            safe_to_drive
        )

        service = self.determine_service(
            problem
        )

        escalation = self.determine_escalation(
            priority
        )

        decision = self.generate_decision(
            priority,
            service,
            safe_to_drive
        )

        user_action = self.generate_user_action(
            problem,
            priority,
            safe_to_drive
        )

        return {

            "priority": priority,

            "service": service,

            "escalation": escalation,

            "safe_to_drive": safe_to_drive,

            "decision": decision,

            "user_action": user_action
        }


# ============================================================
# TEST SUITE
# ============================================================

if __name__ == "__main__":

    engine = DecisionEngine()

    test_cases = [

        {
            "name": "BRAKE FAILURE",
            "problem": "brake_failure",
            "severity": "CRITICAL",
            "safe_to_drive": False,
            "expected_priority": "EMERGENCY",
            "expected_service": "emergency_roadside_assistance",
            "expected_escalation": True
        },

        {
            "name": "ACCIDENT",
            "problem": "accident",
            "severity": "CRITICAL",
            "safe_to_drive": False,
            "expected_priority": "EMERGENCY",
            "expected_service": "emergency_services",
            "expected_escalation": True
        },

        {
            "name": "ENGINE OVERHEATING",
            "problem": "engine_overheating",
            "severity": "CRITICAL",
            "safe_to_drive": False,
            "expected_priority": "EMERGENCY",
            "expected_service": "mechanic_or_roadside_assistance",
            "expected_escalation": True
        },

        {
            "name": "ENGINE FAILURE",
            "problem": "engine_failure",
            "severity": "HIGH",
            "safe_to_drive": False,
            "expected_priority": "URGENT",
            "expected_service": "mechanic_or_roadside_assistance",
            "expected_escalation": False
        },

        {
            "name": "TYRE PUNCTURE",
            "problem": "tyre_puncture",
            "severity": "HIGH",
            "safe_to_drive": False,
            "expected_priority": "URGENT",
            "expected_service": "tyre_assistance",
            "expected_escalation": False
        },

        {
            "name": "BATTERY FAILURE",
            "problem": "battery_failure",
            "severity": "MEDIUM",
            "safe_to_drive": True,
            "expected_priority": "NORMAL",
            "expected_service": "battery_assistance",
            "expected_escalation": False
        },

        {
            "name": "FUEL PROBLEM",
            "problem": "fuel_problem",
            "severity": "MEDIUM",
            "safe_to_drive": True,
            "expected_priority": "NORMAL",
            "expected_service": "fuel_delivery",
            "expected_escalation": False
        },

        {
            "name": "ELECTRICAL FAILURE",
            "problem": "electrical_failure",
            "severity": "MEDIUM",
            "safe_to_drive": True,
            "expected_priority": "NORMAL",
            "expected_service": "electrical_vehicle_assistance",
            "expected_escalation": False
        },

        {
            "name": "UNKNOWN",
            "problem": "unknown",
            "severity": "LOW",
            "safe_to_drive": True,
            "expected_priority": "LOW",
            "expected_service": "general_roadside_assistance",
            "expected_escalation": False
        }
    ]

    print()
    print("=" * 75)
    print("RSA AI DECISION ENGINE - TEST SUITE")
    print("=" * 75)

    passed_tests = 0
    failed_tests = 0

    for test in test_cases:

        print()
        print("-" * 75)

        print(f"TEST              : {test['name']}")

        print(
            f"Expected Priority : "
            f"{test['expected_priority']}"
        )

        print(
            f"Expected Service  : "
            f"{test['expected_service']}"
        )

        print(
            f"Expected Escalation: "
            f"{test['expected_escalation']}"
        )

        try:

            result = engine.make_decision(
                test["problem"],
                test["severity"],
                test["safe_to_drive"]
            )

            priority_match = (
                result["priority"]
                == test["expected_priority"]
            )

            service_match = (
                result["service"]
                == test["expected_service"]
            )

            escalation_match = (
                result["escalation"]
                == test["expected_escalation"]
            )

            if (
                priority_match
                and service_match
                and escalation_match
            ):

                status = "PASS"
                passed_tests += 1

            else:

                status = "FAIL"
                failed_tests += 1

            print(
                f"STATUS            : "
                f"{status}"
            )

            print(
                f"Actual Priority   : "
                f"{result['priority']}"
            )

            print(
                f"Actual Service    : "
                f"{result['service']}"
            )

            print(
                f"Escalation        : "
                f"{result['escalation']}"
            )

            print(
                f"Safe To Drive     : "
                f"{result['safe_to_drive']}"
            )

            print(
                f"Decision          : "
                f"{result['decision']}"
            )

            print(
                f"User Action       : "
                f"{result['user_action']}"
            )

        except Exception as e:

            failed_tests += 1

            print("STATUS            : FAIL")
            print(f"ERROR             : {e}")

    # ---------------------------------------------------------
    # FINAL RESULTS
    # ---------------------------------------------------------

    total_tests = len(test_cases)

    print()
    print("=" * 75)
    print("RSA AI DECISION ENGINE TEST RESULTS")
    print("=" * 75)

    print(
        f"TOTAL TESTS       : "
        f"{total_tests}"
    )

    print(
        f"PASSED            : "
        f"{passed_tests}"
    )

    print(
        f"FAILED            : "
        f"{failed_tests}"
    )

    print("=" * 75)

    if failed_tests == 0:

        print("ALL TESTS PASSED")
        print("RSA DECISION ENGINE IS WORKING CORRECTLY")

    else:

        print("SOME TESTS FAILED")

    print("=" * 75)