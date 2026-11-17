# =============================================================
# RSA AI - VEHICLE HEALTH ENGINE
# =============================================================
# File: ai/vehicle_health.py
#
# Purpose:
#   Evaluates the overall health condition of a vehicle based on
#   incident information, severity, safety status and symptoms.
#
# Output:
#   - health_score
#   - health_status
#   - risk_level
#   - maintenance_required
#   - recommended_action
#   - detected_issues
# =============================================================


import re


class VehicleHealthEngine:

    def __init__(self):

        # ---------------------------------------------------------
        # HEALTH IMPACT SCORES
        # ---------------------------------------------------------

        self.problem_impact = {

            "engine_overheating": 35,

            "brake_failure": 50,

            "tyre_puncture": 25,

            "battery_failure": 15,

            "engine_failure": 45,

            "accident": 50,

            "fuel_problem": 10,

            "electrical_failure": 20,

            "unknown": 5
        }

        # ---------------------------------------------------------
        # KEYWORDS
        # ---------------------------------------------------------

        self.health_patterns = {

            "engine_overheating": [
                "engine hot",
                "engine very hot",
                "engine is hot",
                "engine overheating",
                "overheating",
                "temperature high",
                "temperature warning",
                "coolant",
                "coolant leak",
                "radiator",
                "steam",
                "smoke from engine",
                "smoke coming from engine"
            ],

            "brake_failure": [
                "brake failure",
                "brakes failed",
                "brakes have failed",
                "brakes not working",
                "brake not working",
                "cannot brake",
                "car won't stop",
                "car will not stop",
                "braking problem"
            ],

            "tyre_puncture": [
                "tyre puncture",
                "tire puncture",
                "flat tyre",
                "flat tire",
                "punctured tyre",
                "punctured tire",
                "tyre burst",
                "tire burst"
            ],

            "battery_failure": [
                "battery dead",
                "battery is dead",
                "battery failure",
                "battery problem",
                "car won't start",
                "car will not start",
                "engine won't start",
                "engine will not start",
                "battery warning"
            ],

            "engine_failure": [
                "engine stopped",
                "engine failure",
                "engine failed",
                "engine stalled",
                "engine suddenly stopped",
                "car stopped suddenly",
                "car suddenly stopped"
            ],

            "accident": [
                "accident",
                "crash",
                "collision",
                "hit another car",
                "vehicle hit",
                "car crashed",
                "badly damaged"
            ],

            "fuel_problem": [
                "out of fuel",
                "fuel empty",
                "no fuel",
                "ran out of fuel",
                "run out of fuel",
                "fuel problem"
            ],

            "electrical_failure": [
                "electrical failure",
                "electrical problem",
                "electrical system stopped",
                "wiring problem",
                "lights not working",
                "dashboard went blank",
                "electronics stopped"
            ]
        }

        # ---------------------------------------------------------
        # SEVERITY IMPACT
        # ---------------------------------------------------------

        self.severity_impact = {

            "CRITICAL": 30,

            "HIGH": 20,

            "MEDIUM": 10,

            "LOW": 3
        }

    # =========================================================
    # TEXT NORMALIZATION
    # =========================================================

    def normalize_text(self, text):

        if text is None:
            return ""

        text = str(text).lower().strip()

        # Keep apostrophes because phrases such as
        # "won't start" are useful.
        text = re.sub(r"[^a-z0-9'\s]", " ", text)

        text = re.sub(r"\s+", " ", text)

        return text

    # =========================================================
    # DETECT ISSUES
    # =========================================================

    def detect_issues(self, description):

        text = self.normalize_text(description)

        detected = []

        for problem, patterns in self.health_patterns.items():

            for pattern in patterns:

                if pattern in text:

                    if problem not in detected:

                        detected.append(problem)

                    break

        return detected

    # =========================================================
    # CALCULATE HEALTH SCORE
    # =========================================================

    def calculate_health_score(
        self,
        problem="unknown",
        severity="LOW",
        safe_to_drive=True,
        description=""
    ):

        score = 100

        # -----------------------------------------------------
        # Problem impact
        # -----------------------------------------------------

        problem_impact = self.problem_impact.get(
            problem,
            self.problem_impact["unknown"]
        )

        score -= problem_impact

        # -----------------------------------------------------
        # Severity impact
        # -----------------------------------------------------

        severity = str(severity).upper()

        score -= self.severity_impact.get(
            severity,
            self.severity_impact["LOW"]
        )

        # -----------------------------------------------------
        # Unsafe vehicle penalty
        # -----------------------------------------------------

        if safe_to_drive is False:
            score -= 15

        # -----------------------------------------------------
        # Additional dangerous symptoms
        # -----------------------------------------------------

        text = self.normalize_text(description)

        dangerous_keywords = [
            "fire",
            "flames",
            "explosion",
            "smoke",
            "fuel leak"
        ]

        for keyword in dangerous_keywords:

            if keyword in text:

                score -= 10
                break

        # -----------------------------------------------------
        # Keep score between 0 and 100
        # -----------------------------------------------------

        score = max(0, min(100, score))

        return score

    # =========================================================
    # DETERMINE HEALTH STATUS
    # =========================================================

    def determine_health_status(self, health_score):

        if health_score >= 80:

            return "GOOD"

        if health_score >= 60:

            return "FAIR"

        if health_score >= 40:

            return "POOR"

        return "CRITICAL"

    # =========================================================
    # DETERMINE RISK LEVEL
    # =========================================================

    def determine_risk_level(
        self,
        health_score,
        severity="LOW",
        safe_to_drive=True
    ):

        severity = str(severity).upper()

        if severity == "CRITICAL":

            return "CRITICAL"

        if not safe_to_drive:

            if severity == "HIGH":

                return "HIGH"

            return "HIGH"

        if health_score < 40:

            return "HIGH"

        if health_score < 60:

            return "MEDIUM"

        if health_score < 80:

            return "LOW"

        return "LOW"

    # =========================================================
    # MAINTENANCE DECISION
    # =========================================================

    def determine_maintenance(
        self,
        problem,
        severity,
        safe_to_drive
    ):

        severity = str(severity).upper()

        if problem in [
            "brake_failure",
            "engine_overheating",
            "engine_failure",
            "accident"
        ]:

            return True

        if severity in [
            "CRITICAL",
            "HIGH"
        ]:

            return True

        if problem in [
            "tyre_puncture",
            "battery_failure",
            "electrical_failure"
        ]:

            return True

        return False

    # =========================================================
    # RECOMMENDED HEALTH ACTION
    # =========================================================

    def determine_action(
        self,
        problem,
        health_status,
        safe_to_drive
    ):

        # -----------------------------------------------------
        # Critical problems
        # -----------------------------------------------------

        if problem == "brake_failure":

            return (
                "Do not drive the vehicle. "
                "Arrange immediate brake inspection and "
                "emergency roadside assistance."
            )

        if problem == "engine_overheating":

            return (
                "Stop driving when safe to do so. "
                "Allow the engine to cool and arrange "
                "professional inspection or roadside assistance."
            )

        if problem == "engine_failure":

            return (
                "Do not continue normal driving. "
                "Move to a safe location and arrange "
                "professional engine inspection."
            )

        if problem == "accident":

            return (
                "Do not continue driving until the vehicle "
                "has been inspected for accident-related damage."
            )

        # -----------------------------------------------------
        # Other problems
        # -----------------------------------------------------

        if problem == "tyre_puncture":

            return (
                "Inspect or replace the damaged tyre before "
                "resuming normal driving."
            )

        if problem == "battery_failure":

            return (
                "Check the battery and charging system. "
                "Arrange battery assistance or professional inspection."
            )

        if problem == "fuel_problem":

            return (
                "Refuel the vehicle and inspect the fuel system "
                "if the problem occurs repeatedly."
            )

        if problem == "electrical_failure":

            return (
                "Have the vehicle electrical system inspected "
                "before continuing normal use."
            )

        # -----------------------------------------------------
        # Health status
        # -----------------------------------------------------

        if health_status == "GOOD":

            return (
                "Vehicle health appears good. "
                "Continue normal maintenance and monitoring."
            )

        if health_status == "FAIR":

            return (
                "Vehicle condition is fair. "
                "Schedule a professional inspection if symptoms continue."
            )

        if health_status == "POOR":

            return (
                "Vehicle requires professional inspection "
                "before extended driving."
            )

        return (
            "Vehicle health is critical. "
            "Do not continue driving and arrange professional assistance."
        )

    # =========================================================
    # COMPLETE VEHICLE HEALTH ANALYSIS
    # =========================================================

    def analyze(
        self,
        description="",
        problem="unknown",
        severity="LOW",
        safe_to_drive=True
    ):

        description = description or ""

        # -----------------------------------------------------
        # Automatically detect problem if unknown
        # -----------------------------------------------------

        detected_issues = self.detect_issues(description)

        if problem == "unknown" and detected_issues:

            # Choose the strongest issue based on impact.
            problem = max(
                detected_issues,
                key=lambda item: self.problem_impact.get(
                    item,
                    0
                )
            )

        # -----------------------------------------------------
        # Calculate health
        # -----------------------------------------------------

        health_score = self.calculate_health_score(
            problem=problem,
            severity=severity,
            safe_to_drive=safe_to_drive,
            description=description
        )

        # -----------------------------------------------------
        # Health status
        # -----------------------------------------------------

        health_status = self.determine_health_status(
            health_score
        )

        # -----------------------------------------------------
        # Risk
        # -----------------------------------------------------

        risk_level = self.determine_risk_level(
            health_score=health_score,
            severity=severity,
            safe_to_drive=safe_to_drive
        )

        # -----------------------------------------------------
        # Maintenance
        # -----------------------------------------------------

        maintenance_required = self.determine_maintenance(
            problem=problem,
            severity=severity,
            safe_to_drive=safe_to_drive
        )

        # -----------------------------------------------------
        # Recommended action
        # -----------------------------------------------------

        recommended_action = self.determine_action(
            problem=problem,
            health_status=health_status,
            safe_to_drive=safe_to_drive
        )

        # -----------------------------------------------------
        # Return result
        # -----------------------------------------------------

        return {

            "problem": problem,

            "health_score": health_score,

            "health_status": health_status,

            "risk_level": risk_level,

            "maintenance_required": maintenance_required,

            "safe_to_drive": safe_to_drive,

            "detected_issues": detected_issues,

            "recommended_action": recommended_action,

            # ----- additive transparency fields -----
            # The score is derived from the reported incident only. The RSA
            # project has no vehicle sensor/OBD data source, so this must never
            # be presented as a measured vehicle condition.
            "basis": "incident_report",
            "sensor_data_used": False,
            "limitations": (
                "Indicator derived from the reported incident text and its severity. "
                "No sensor, OBD-II or maintenance data was used; it is not a measured "
                "vehicle health reading."
            ),
        }


# =============================================================
# TEST SUITE
# =============================================================

if __name__ == "__main__":

    engine = VehicleHealthEngine()

    test_cases = [

        (
            "ENGINE OVERHEATING",
            "My engine is very hot and there is smoke coming from the engine.",
            "engine_overheating",
            "CRITICAL",
            False
        ),

        (
            "BRAKE FAILURE",
            "My brakes have completely failed and the car won't stop.",
            "brake_failure",
            "CRITICAL",
            False
        ),

        (
            "TYRE PUNCTURE",
            "I have a flat tyre and my car is shaking.",
            "tyre_puncture",
            "HIGH",
            False
        ),

        (
            "BATTERY FAILURE",
            "My battery is dead and the car won't start.",
            "battery_failure",
            "MEDIUM",
            True
        ),

        (
            "ACCIDENT",
            "I was involved in a collision and my car is badly damaged.",
            "accident",
            "CRITICAL",
            False
        ),

        (
            "FUEL PROBLEM",
            "My car has run out of fuel and stopped.",
            "fuel_problem",
            "MEDIUM",
            True
        ),

        (
            "ELECTRICAL FAILURE",
            "The dashboard went blank and the electrical system stopped.",
            "electrical_failure",
            "MEDIUM",
            True
        ),

        (
            "ENGINE FAILURE",
            "The engine suddenly stopped while I was driving.",
            "engine_failure",
            "HIGH",
            False
        ),

        (
            "UNKNOWN",
            "My car is making a strange sound.",
            "unknown",
            "LOW",
            True
        )
    ]

    print()
    print("=" * 75)
    print("RSA VEHICLE HEALTH ENGINE - TEST SUITE")
    print("=" * 75)

    passed_tests = 0
    failed_tests = 0

    for (
        test_name,
        description,
        expected_problem,
        severity,
        safe_to_drive
    ) in test_cases:

        print()
        print("-" * 75)

        print(f"TEST              : {test_name}")

        try:

            result = engine.analyze(
                description=description,
                problem=expected_problem,
                severity=severity,
                safe_to_drive=safe_to_drive
            )

            actual_problem = result["problem"]

            if actual_problem == expected_problem:

                status = "PASS"
                passed_tests += 1

            else:

                status = "FAIL"
                failed_tests += 1

            print(f"STATUS            : {status}")

            print(
                f"Expected Problem  : "
                f"{expected_problem}"
            )

            print(
                f"Actual Problem    : "
                f"{actual_problem}"
            )

            print(
                f"Health Score      : "
                f"{result['health_score']}"
            )

            print(
                f"Health Status     : "
                f"{result['health_status']}"
            )

            print(
                f"Risk Level        : "
                f"{result['risk_level']}"
            )

            print(
                f"Maintenance       : "
                f"{result['maintenance_required']}"
            )

            print(
                f"Safe To Drive     : "
                f"{result['safe_to_drive']}"
            )

            print(
                f"Detected Issues   : "
                f"{result['detected_issues']}"
            )

            print("Recommended Action:")

            print(
                f"  {result['recommended_action']}"
            )

        except Exception as error:

            failed_tests += 1

            print("STATUS            : FAIL")
            print(f"ERROR             : {error}")

    # =========================================================
    # FINAL RESULTS
    # =========================================================

    total_tests = len(test_cases)

    print()
    print("=" * 75)
    print("RSA VEHICLE HEALTH ENGINE TEST RESULTS")
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

        print(
            "RSA VEHICLE HEALTH ENGINE "
            "IS WORKING CORRECTLY"
        )

    else:

        print("SOME TESTS FAILED")

    print("=" * 75)