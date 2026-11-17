# ============================================================
# RSA AI - SAFETY RISK ENGINE
# ============================================================


class SafetyRiskEngine:

    def __init__(self):

        # ----------------------------------------------------
        # PROBLEMS THAT SHOULD NOT BE DRIVEN
        # ----------------------------------------------------

        self.unsafe_problems = {

            "brake_failure",
            "engine_overheating",
            "engine_failure"
        }

        # ----------------------------------------------------
        # PROBLEMS THAT REQUIRE CAUTION
        # ----------------------------------------------------

        self.caution_problems = {

            "tyre_puncture",
            "battery_failure",
            "fuel_problem",
            "electrical_failure"
        }

        # ----------------------------------------------------
        # CRITICAL KEYWORDS
        # ----------------------------------------------------

        self.critical_keywords = [

            "fire",
            "flames",
            "smoke",
            "fuel leak",
            "brakes failed",
            "brake failure",
            "cannot brake",
            "car won't stop",
            "car will not stop",
            "accident",
            "crash",
            "collision",
            "explosion"
        ]

        # ----------------------------------------------------
        # HIGH-RISK KEYWORDS
        # ----------------------------------------------------

        self.high_risk_keywords = [

            "overheating",
            "engine very hot",
            "engine hot",
            "coolant leak",
            "tyre burst",
            "tire burst",
            "flat tyre",
            "flat tire",
            "engine failure",
            "engine stopped",
            "engine suddenly stopped"
        ]

    # --------------------------------------------------------
    # NORMALIZE TEXT
    # --------------------------------------------------------

    def normalize_text(self, text):

        if not text:
            return ""

        return " ".join(
            str(text).lower().strip().split()
        )

    # --------------------------------------------------------
    # CHECK KEYWORD
    # --------------------------------------------------------

    def contains_keyword(self, text, keyword):

        return keyword in text

    # --------------------------------------------------------
    # DETERMINE RISK LEVEL
    # --------------------------------------------------------

    def determine_risk(
        self,
        problem,
        severity,
        description
    ):

        text = self.normalize_text(
            description
        )

        severity = (
            str(severity).upper()
            if severity
            else "LOW"
        )

        # ----------------------------------------------------
        # CRITICAL RISK
        # ----------------------------------------------------

        for keyword in self.critical_keywords:

            if self.contains_keyword(
                text,
                keyword
            ):

                return "CRITICAL"

        if severity == "CRITICAL":

            return "CRITICAL"

        # ----------------------------------------------------
        # HIGH RISK
        # ----------------------------------------------------

        if problem in self.unsafe_problems:

            return "HIGH"

        for keyword in self.high_risk_keywords:

            if self.contains_keyword(
                text,
                keyword
            ):

                return "HIGH"

        if severity == "HIGH":

            return "HIGH"

        # ----------------------------------------------------
        # MEDIUM RISK
        # ----------------------------------------------------

        if problem in self.caution_problems:

            return "MEDIUM"

        if severity == "MEDIUM":

            return "MEDIUM"

        # ----------------------------------------------------
        # LOW RISK
        # ----------------------------------------------------

        return "LOW"

    # --------------------------------------------------------
    # DETERMINE SAFE TO DRIVE
    # --------------------------------------------------------

    def is_safe_to_drive(
        self,
        problem,
        severity,
        description
    ):

        risk = self.determine_risk(
            problem,
            severity,
            description
        )

        # Critical and high-risk incidents
        # should not continue driving.

        if risk in [
            "CRITICAL",
            "HIGH"
        ]:

            return False

        # Explicit unsafe problems

        if problem in self.unsafe_problems:

            return False

        return True

    # --------------------------------------------------------
    # SAFETY REASON
    # --------------------------------------------------------

    def get_safety_reason(
        self,
        problem,
        severity,
        safe_to_drive
    ):

        if not safe_to_drive:

            if problem == "brake_failure":

                return (
                    "Brake failure can prevent the vehicle "
                    "from stopping safely."
                )

            if problem == "engine_overheating":

                return (
                    "Continued driving with an overheating "
                    "engine may cause serious engine damage "
                    "or create a safety hazard."
                )

            if problem == "engine_failure":

                return (
                    "An unexpected engine failure can leave "
                    "the vehicle disabled and unsafe to continue driving."
                )

            if problem == "accident":

                return (
                    "A collision may have caused hidden "
                    "mechanical or structural damage."
                )

            return (
                "The detected incident presents a safety risk "
                "and the vehicle should not continue normal driving."
            )

        if problem == "tyre_puncture":

            return (
                "A damaged tyre can affect vehicle control. "
                "Move to a safe location and arrange tyre assistance."
            )

        if problem == "battery_failure":

            return (
                "The vehicle may not start reliably. "
                "Battery or charging-system assistance is recommended."
            )

        if problem == "fuel_problem":

            return (
                "The vehicle has a fuel-related problem. "
                "Fuel delivery assistance may be required."
            )

        if problem == "electrical_failure":

            return (
                "An electrical problem may affect vehicle systems. "
                "Professional inspection is recommended."
            )

        return (
            "No immediate high-risk condition was identified "
            "from the provided information."
        )

    # --------------------------------------------------------
    # SAFETY ACTION
    # --------------------------------------------------------

    def get_safety_action(
        self,
        problem,
        safe_to_drive
    ):

        if not safe_to_drive:

            if problem == "brake_failure":

                return (
                    "Do not continue driving. Move to a safe "
                    "location if possible and request emergency "
                    "roadside assistance."
                )

            if problem == "engine_overheating":

                return (
                    "Stop driving immediately. Move to a safe "
                    "location, switch off the engine, stay away "
                    "from steam or smoke, and request roadside assistance."
                )

            if problem == "accident":

                return (
                    "Move to a safe location if possible, check "
                    "for injuries, and contact emergency services "
                    "or roadside assistance."
                )

            return (
                "Stop driving when it is safe to do so, move to "
                "a safe location, and request roadside assistance."
            )

        if problem == "tyre_puncture":

            return (
                "Slow down safely and move to a safe location. "
                "Do not continue driving on a severely damaged "
                "or flat tyre."
            )

        if problem == "battery_failure":

            return (
                "Move to a safe location and request battery "
                "jump-start or roadside assistance."
            )

        if problem == "fuel_problem":

            return (
                "Move to a safe location and request fuel "
                "delivery or roadside assistance."
            )

        if problem == "electrical_failure":

            return (
                "Stop in a safe location and request vehicle "
                "inspection or roadside assistance."
            )

        return (
            "No immediate safety restriction was identified. "
            "Drive carefully and seek professional diagnosis "
            "if the issue continues."
        )

    # --------------------------------------------------------
    # COMPLETE SAFETY ASSESSMENT
    # --------------------------------------------------------

    def assess(
        self,
        problem,
        severity,
        description
    ):

        risk_level = self.determine_risk(
            problem,
            severity,
            description
        )

        safe_to_drive = self.is_safe_to_drive(
            problem,
            severity,
            description
        )

        reason = self.get_safety_reason(
            problem,
            severity,
            safe_to_drive
        )

        action = self.get_safety_action(
            problem,
            safe_to_drive
        )

        return {

            "risk_level": risk_level,

            "safe_to_drive": safe_to_drive,

            "reason": reason,

            "recommended_action": action
        }


# ============================================================
# TEST SUITE
# ============================================================

if __name__ == "__main__":

    engine = SafetyRiskEngine()

    test_cases = [

        (
            "ENGINE OVERHEATING",
            "engine_overheating",
            "CRITICAL",
            "My engine is very hot and there is smoke coming from the engine.",
            "CRITICAL",
            False
        ),

        (
            "BRAKE FAILURE",
            "brake_failure",
            "CRITICAL",
            "My brakes have completely failed and the car won't stop.",
            "CRITICAL",
            False
        ),

        (
            "TYRE PUNCTURE",
            "tyre_puncture",
            "HIGH",
            "I have a flat tyre.",
            "HIGH",
            False
        ),

        (
            "BATTERY FAILURE",
            "battery_failure",
            "MEDIUM",
            "My battery is dead and the car won't start.",
            "MEDIUM",
            True
        ),

        (
            "ACCIDENT",
            "accident",
            "CRITICAL",
            "I was involved in a collision.",
            "CRITICAL",
            False
        ),

        (
            "FUEL PROBLEM",
            "fuel_problem",
            "MEDIUM",
            "My car has run out of fuel.",
            "MEDIUM",
            True
        ),

        (
            "ELECTRICAL FAILURE",
            "electrical_failure",
            "MEDIUM",
            "The dashboard went blank and the electrical system stopped.",
            "MEDIUM",
            True
        ),

        (
            "ENGINE FAILURE",
            "engine_failure",
            "HIGH",
            "The engine suddenly stopped while driving.",
            "HIGH",
            False
        ),

        (
            "UNKNOWN",
            "unknown",
            "LOW",
            "My car is making a strange sound.",
            "LOW",
            True
        )
    ]

    print()
    print("=" * 75)
    print("RSA AI SAFETY RISK ENGINE - TEST SUITE")
    print("=" * 75)

    total_tests = 0
    passed_tests = 0
    failed_tests = 0

    for (
        test_name,
        problem,
        severity,
        description,
        expected_risk,
        expected_safe
    ) in test_cases:

        total_tests += 1

        print()
        print("-" * 75)
        print(f"TEST              : {test_name}")
        print(f"Expected Risk     : {expected_risk}")
        print(f"Expected Safe     : {expected_safe}")

        try:

            result = engine.assess(
                problem,
                severity,
                description
            )

            actual_risk = result["risk_level"]
            actual_safe = result["safe_to_drive"]

            if (
                actual_risk == expected_risk
                and actual_safe == expected_safe
            ):

                passed_tests += 1

                print("STATUS            : PASS")

            else:

                failed_tests += 1

                print("STATUS            : FAIL")

            print(
                f"Actual Risk       : {actual_risk}"
            )

            print(
                f"Safe To Drive     : {actual_safe}"
            )

            print(
                f"Reason            : {result['reason']}"
            )

            print(
                f"Recommended Action:"
            )

            print(
                f"  {result['recommended_action']}"
            )

        except Exception as e:

            failed_tests += 1

            print("STATUS            : ERROR")
            print(f"Error             : {e}")

    print()
    print("=" * 75)
    print("RSA AI SAFETY RISK TEST RESULTS")
    print("=" * 75)

    print(
        f"TOTAL TESTS       : {total_tests}"
    )

    print(
        f"PASSED            : {passed_tests}"
    )

    print(
        f"FAILED            : {failed_tests}"
    )

    print("=" * 75)

    if failed_tests == 0:

        print("ALL TESTS PASSED")
        print("RSA SAFETY RISK ENGINE IS WORKING CORRECTLY")

    else:

        print("SOME TESTS FAILED")

    print("=" * 75)