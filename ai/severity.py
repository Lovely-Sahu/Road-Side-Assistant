# ============================================================
# RSA AI - SEVERITY ENGINE
# ============================================================

try:
    # Used when imported as a package
    from .incident_analyzer import IncidentAnalyzer
except ImportError:
    # Used when running directly:
    # python ai/severity.py
    from incident_analyzer import IncidentAnalyzer


class SeverityEngine:

    def __init__(self):

        self.severity_levels = {
            "CRITICAL": 4,
            "HIGH": 3,
            "MEDIUM": 2,
            "LOW": 1
        }

    # --------------------------------------------------------
    # DETERMINE SEVERITY
    # --------------------------------------------------------

    def determine(
        self,
        description,
        problem="unknown"
    ):

        analyzer = IncidentAnalyzer()

        severity = analyzer.determine_severity(
            description,
            problem
        )

        return severity

    # --------------------------------------------------------
    # GET SEVERITY SCORE
    # --------------------------------------------------------

    def get_score(self, severity):

        if not severity:
            return 1

        return self.severity_levels.get(
            severity.upper(),
            1
        )

    # --------------------------------------------------------
    # GET SEVERITY INFORMATION
    # --------------------------------------------------------

    def get_details(self, severity):

        if not severity:
            severity = "LOW"

        severity = severity.upper()

        details = {

            "CRITICAL": {
                "score": 4,
                "label": "Critical",
                "description": (
                    "Immediate danger or emergency condition. "
                    "Emergency assistance may be required."
                )
            },

            "HIGH": {
                "score": 3,
                "label": "High",
                "description": (
                    "The vehicle should generally not continue "
                    "normal driving. Roadside assistance is recommended."
                )
            },

            "MEDIUM": {
                "score": 2,
                "label": "Medium",
                "description": (
                    "The vehicle has a problem that requires "
                    "attention but may not represent an immediate emergency."
                )
            },

            "LOW": {
                "score": 1,
                "label": "Low",
                "description": (
                    "No immediate high-risk condition was identified "
                    "from the provided information."
                )
            }
        }

        return details.get(
            severity,
            details["LOW"]
        )

    # --------------------------------------------------------
    # COMPLETE ASSESSMENT
    # --------------------------------------------------------

    def assess(
        self,
        description,
        problem="unknown"
    ):

        severity = self.determine(
            description,
            problem
        )

        details = self.get_details(
            severity
        )

        return {
            "severity": severity,
            "score": details["score"],
            "label": details["label"],
            "description": details["description"]
        }


# ============================================================
# TEST SUITE
# ============================================================

if __name__ == "__main__":

    engine = SeverityEngine()

    test_cases = [

        (
            "ENGINE OVERHEATING",
            "My engine is very hot and there is smoke coming from the engine.",
            "engine_overheating",
            "CRITICAL"
        ),

        (
            "BRAKE FAILURE",
            "My brakes have completely failed and the car won't stop.",
            "brake_failure",
            "CRITICAL"
        ),

        (
            "TYRE PUNCTURE",
            "I have a flat tyre.",
            "tyre_puncture",
            "HIGH"
        ),

        (
            "BATTERY FAILURE",
            "My battery is dead and the car won't start.",
            "battery_failure",
            "MEDIUM"
        ),

        (
            "ACCIDENT",
            "I was involved in a collision.",
            "accident",
            "CRITICAL"
        ),

        (
            "FUEL PROBLEM",
            "My car has run out of fuel.",
            "fuel_problem",
            "MEDIUM"
        ),

        (
            "ENGINE FAILURE",
            "The engine suddenly stopped while driving.",
            "engine_failure",
            "HIGH"
        ),

        (
            "UNKNOWN",
            "My car is making a strange sound.",
            "unknown",
            "LOW"
        )
    ]

    print()
    print("=" * 75)
    print("RSA AI SEVERITY ENGINE - TEST SUITE")
    print("=" * 75)

    total_tests = 0
    passed_tests = 0
    failed_tests = 0

    for (
        test_name,
        description,
        problem,
        expected
    ) in test_cases:

        total_tests += 1

        print()
        print("-" * 75)
        print(f"TEST              : {test_name}")
        print(f"Expected Severity : {expected}")

        try:

            result = engine.assess(
                description,
                problem
            )

            actual = result["severity"]

            if actual == expected:

                passed_tests += 1

                print("STATUS            : PASS")

            else:

                failed_tests += 1

                print("STATUS            : FAIL")

            print(f"Actual Severity   : {actual}")
            print(f"Severity Score    : {result['score']}")
            print(f"Label             : {result['label']}")
            print(f"Description       : {result['description']}")

        except Exception as e:

            failed_tests += 1

            print("STATUS            : ERROR")
            print(f"Error             : {e}")

    print()
    print("=" * 75)
    print("RSA AI SEVERITY TEST RESULTS")
    print("=" * 75)

    print(f"TOTAL TESTS       : {total_tests}")
    print(f"PASSED            : {passed_tests}")
    print(f"FAILED            : {failed_tests}")

    print("=" * 75)

    if failed_tests == 0:

        print("ALL TESTS PASSED")
        print("RSA SEVERITY ENGINE IS WORKING CORRECTLY")

    else:

        print("SOME TESTS FAILED")

    print("=" * 75)