# =============================================================
# RSA AI - VEHICLE VISION ENGINE
# =============================================================
# File: ai/vision.py
#
# Purpose:
#   Analyze vehicle incident images using image metadata,
#   filenames and optional externally supplied visual labels.
#
#   This module is intentionally dependency-free so the RSA
#   project can run without OpenCV/TensorFlow installation.
#
# Main output:
#   - detected_problem
#   - confidence
#   - severity
#   - safe_to_drive
#   - visual_findings
#   - recommended_action
# =============================================================


import os
import re


class VehicleVisionEngine:

    def __init__(self):

        # ---------------------------------------------------------
        # VISUAL PROBLEM PATTERNS
        # ---------------------------------------------------------

        self.visual_patterns = {

            "engine_overheating": [
                "overheating",
                "overheated",
                "engine hot",
                "hot engine",
                "steam",
                "coolant leak",
                "coolant",
                "radiator",
                "engine smoke",
                "smoke from engine",
                "smoke coming from engine"
            ],

            "brake_failure": [
                "brake failure",
                "brake failed",
                "brakes failed",
                "brake damage",
                "brake problem"
            ],

            "tyre_puncture": [
                "tyre puncture",
                "tire puncture",
                "flat tyre",
                "flat tire",
                "punctured tyre",
                "punctured tire",
                "tyre damage",
                "tire damage",
                "tyre burst",
                "tire burst"
            ],

            "battery_failure": [
                "battery failure",
                "dead battery",
                "battery damage",
                "battery problem"
            ],

            "engine_failure": [
                "engine failure",
                "engine damage",
                "engine stopped",
                "engine problem",
                "engine fault"
            ],

            "accident": [
                "accident",
                "crash",
                "collision",
                "damaged car",
                "vehicle damage",
                "front damage",
                "rear damage",
                "side damage",
                "badly damaged"
            ],

            "fuel_problem": [
                "fuel problem",
                "fuel leak",
                "empty fuel",
                "out of fuel"
            ],

            "electrical_failure": [
                "electrical failure",
                "electrical problem",
                "wiring damage",
                "electrical damage",
                "dashboard failure",
                "lights failure"
            ]
        }

        # ---------------------------------------------------------
        # SEVERITY KEYWORDS
        # ---------------------------------------------------------

        self.critical_keywords = [
            "fire",
            "flames",
            "explosion",
            "heavy smoke",
            "major collision",
            "severe accident",
            "brake failure",
            "brakes failed",
            "fuel leak"
        ]

        self.high_keywords = [
            "overheating",
            "overheated",
            "engine smoke",
            "smoke from engine",
            "coolant leak",
            "tyre burst",
            "tire burst",
            "tyre puncture",
            "tire puncture",
            "engine failure",
            "engine damage",
            "badly damaged"
        ]

        self.medium_keywords = [
            "battery",
            "electrical",
            "wiring",
            "dashboard",
            "fuel problem",
            "tyre damage",
            "tire damage"
        ]

    # =========================================================
    # TEXT NORMALIZATION
    # =========================================================

    def normalize_text(self, text):

        if text is None:
            return ""

        text = str(text).lower().strip()

        text = re.sub(
            r"[^a-z0-9'\s]",
            " ",
            text
        )

        text = re.sub(
            r"\s+",
            " ",
            text
        )

        return text

    # =========================================================
    # EXTRACT IMAGE NAME
    # =========================================================

    def extract_image_name(self, image_path):

        if not image_path:
            return ""

        try:

            filename = os.path.basename(
                str(image_path)
            )

            filename = os.path.splitext(
                filename
            )[0]

            return self.normalize_text(filename)

        except Exception:

            return ""

    # =========================================================
    # DETECT VISUAL PROBLEM
    # =========================================================

    def detect_problem(
        self,
        image_path=None,
        visual_description=""
    ):

        image_text = self.extract_image_name(
            image_path
        )

        description_text = self.normalize_text(
            visual_description
        )

        combined_text = (
            image_text + " " + description_text
        ).strip()

        if not combined_text:

            return {
                "problem": "unknown",
                "confidence": 0.0,
                "matched_keywords": []
            }

        scores = {}
        matches = {}

        # -----------------------------------------------------
        # Match every visual category
        # -----------------------------------------------------

        for problem, patterns in self.visual_patterns.items():

            score = 0
            problem_matches = []

            for pattern in patterns:

                if pattern in combined_text:

                    problem_matches.append(pattern)

                    # Longer phrases provide stronger evidence.
                    score += 1 + (
                        len(pattern.split()) * 0.20
                    )

            if score > 0:

                scores[problem] = score
                matches[problem] = problem_matches

        # -----------------------------------------------------
        # Unknown image
        # -----------------------------------------------------

        if not scores:

            return {
                "problem": "unknown",
                "confidence": 0.0,
                "matched_keywords": []
            }

        # -----------------------------------------------------
        # Select strongest problem
        # -----------------------------------------------------

        best_problem = max(
            scores,
            key=scores.get
        )

        best_matches = matches[
            best_problem
        ]

        # -----------------------------------------------------
        # Calculate confidence
        # -----------------------------------------------------

        confidence = 0.60

        if len(best_matches) >= 2:

            confidence += 0.08

        if len(best_matches) >= 3:

            confidence += 0.07

        if scores[best_problem] >= 3:

            confidence += 0.05

        confidence = min(
            round(confidence, 2),
            0.99
        )

        return {
            "problem": best_problem,
            "confidence": confidence,
            "matched_keywords": best_matches
        }

    # =========================================================
    # DETECT SEVERITY
    # =========================================================

    def determine_severity(
        self,
        visual_description="",
        problem="unknown"
    ):

        text = self.normalize_text(
            visual_description
        )

        for keyword in self.critical_keywords:

            if keyword in text:

                return "CRITICAL"

        for keyword in self.high_keywords:

            if keyword in text:

                return "HIGH"

        for keyword in self.medium_keywords:

            if keyword in text:

                return "MEDIUM"

        # -----------------------------------------------------
        # Problem-based fallback
        # -----------------------------------------------------

        if problem in [
            "brake_failure",
            "accident"
        ]:

            return "CRITICAL"

        if problem in [
            "engine_overheating",
            "engine_failure",
            "tyre_puncture"
        ]:

            return "HIGH"

        if problem in [
            "battery_failure",
            "fuel_problem",
            "electrical_failure"
        ]:

            return "MEDIUM"

        return "LOW"

    # =========================================================
    # SAFETY ASSESSMENT
    # =========================================================

    def determine_safety(
        self,
        problem,
        severity,
        visual_description=""
    ):

        text = self.normalize_text(
            visual_description
        )

        dangerous_keywords = [

            "fire",
            "flames",
            "explosion",
            "heavy smoke",
            "brake failure",
            "brakes failed",
            "fuel leak",
            "major collision",
            "severe accident",
            "overheating",
            "engine overheating",
            "engine failure",
            "tyre burst",
            "tire burst",
            "tyre puncture",
            "tire puncture"
        ]

        for keyword in dangerous_keywords:

            if keyword in text:

                return False

        if severity in [
            "CRITICAL",
            "HIGH"
        ]:

            return False

        if problem in [
            "brake_failure",
            "engine_overheating",
            "engine_failure",
            "accident",
            "tyre_puncture"
        ]:

            return False

        return True

    # =========================================================
    # VISUAL FINDINGS
    # =========================================================

    def generate_findings(
        self,
        problem,
        matched_keywords
    ):

        if problem == "engine_overheating":

            return [
                "Possible engine overheating detected.",
                "Visible heat, steam or coolant-related symptoms may be present."
            ]

        if problem == "brake_failure":

            return [
                "Possible brake-system problem detected.",
                "Brake components should be professionally inspected."
            ]

        if problem == "tyre_puncture":

            return [
                "Possible tyre damage detected.",
                "Tyre condition should be checked before driving."
            ]

        if problem == "battery_failure":

            return [
                "Possible battery-related problem detected.",
                "Battery and charging system should be inspected."
            ]

        if problem == "engine_failure":

            return [
                "Possible engine failure detected.",
                "Professional mechanical inspection is recommended."
            ]

        if problem == "accident":

            return [
                "Possible accident or vehicle damage detected.",
                "Vehicle should be inspected before normal driving."
            ]

        if problem == "fuel_problem":

            return [
                "Possible fuel-system problem detected.",
                "Fuel level and fuel system should be checked."
            ]

        if problem == "electrical_failure":

            return [
                "Possible electrical-system problem detected.",
                "Electrical wiring and components should be inspected."
            ]

        return [
            "No specific vehicle problem could be identified from the available visual information."
        ]

    # =========================================================
    # RECOMMENDED ACTION
    # =========================================================

    def determine_action(
        self,
        problem,
        severity,
        safe_to_drive
    ):

        if problem == "engine_overheating":

            return (
                "Stop driving when safe to do so, switch off "
                "the engine and request roadside assistance."
            )

        if problem == "brake_failure":

            return (
                "Do not continue driving. Request emergency "
                "roadside assistance."
            )

        if problem == "tyre_puncture":

            return (
                "Slow down safely, move to a safe location "
                "and request tyre or roadside assistance."
            )

        if problem == "battery_failure":

            return (
                "Request battery assistance or professional "
                "vehicle inspection."
            )

        if problem == "engine_failure":

            return (
                "Move to a safe location if possible and "
                "request roadside assistance."
            )

        if problem == "accident":

            return (
                "Check for injuries, move to a safe location "
                "if possible and contact emergency services."
            )

        if problem == "fuel_problem":

            return (
                "Move to a safe location and request fuel "
                "delivery or roadside assistance."
            )

        if problem == "electrical_failure":

            return (
                "Stop in a safe location and arrange "
                "professional vehicle inspection."
            )

        return (
            "No specific visual problem was detected. "
            "Seek professional diagnosis if the issue continues."
        )

    # =========================================================
    # COMPLETE VISION ANALYSIS
    # =========================================================

    def analyze(
        self,
        image_path=None,
        visual_description=""
    ):

        detected = self.detect_problem(
            image_path=image_path,
            visual_description=visual_description
        )

        problem = detected["problem"]

        confidence = detected["confidence"]

        matched_keywords = detected[
            "matched_keywords"
        ]

        severity = self.determine_severity(
            visual_description=visual_description,
            problem=problem
        )

        safe_to_drive = self.determine_safety(
            problem=problem,
            severity=severity,
            visual_description=visual_description
        )

        visual_findings = self.generate_findings(
            problem=problem,
            matched_keywords=matched_keywords
        )

        recommended_action = self.determine_action(
            problem=problem,
            severity=severity,
            safe_to_drive=safe_to_drive
        )

        return {

            "detected_problem": problem,

            "problem": problem,

            "confidence": confidence,

            "severity": severity,

            "safe_to_drive": safe_to_drive,

            "matched_keywords": matched_keywords,

            "visual_findings": visual_findings,

            "recommended_action": recommended_action
        }


# =============================================================
# TEST SUITE
# =============================================================

if __name__ == "__main__":

    engine = VehicleVisionEngine()

    test_cases = [

        (
            "ENGINE OVERHEATING",
            "engine_overheating.jpg",
            "The engine is very hot with steam coming from the engine.",
            "engine_overheating"
        ),

        (
            "BRAKE FAILURE",
            "brake_failure.jpg",
            "The brakes have failed and there is visible brake damage.",
            "brake_failure"
        ),

        (
            "TYRE PUNCTURE",
            "flat_tyre.jpg",
            "The vehicle has a flat tyre and visible tyre damage.",
            "tyre_puncture"
        ),

        (
            "BATTERY FAILURE",
            "dead_battery.jpg",
            "The vehicle has a dead battery.",
            "battery_failure"
        ),

        (
            "ACCIDENT",
            "car_collision.jpg",
            "The vehicle has major collision damage.",
            "accident"
        ),

        (
            "FUEL PROBLEM",
            "fuel_problem.jpg",
            "The vehicle has a fuel problem.",
            "fuel_problem"
        ),

        (
            "ELECTRICAL FAILURE",
            "electrical_damage.jpg",
            "The electrical system has visible damage.",
            "electrical_failure"
        ),

        (
            "ENGINE FAILURE",
            "engine_failure.jpg",
            "The engine has failed and shows engine damage.",
            "engine_failure"
        ),

        (
            "UNKNOWN",
            "vehicle_photo.jpg",
            "A normal vehicle photo without a clearly identifiable problem.",
            "unknown"
        )
    ]

    print()
    print("=" * 75)
    print("RSA AI VEHICLE VISION ENGINE - TEST SUITE")
    print("=" * 75)

    passed_tests = 0
    failed_tests = 0

    for (
        test_name,
        image_path,
        description,
        expected_problem
    ) in test_cases:

        print()
        print("-" * 75)

        print(
            f"TEST              : {test_name}"
        )

        try:

            result = engine.analyze(
                image_path=image_path,
                visual_description=description
            )

            actual_problem = result[
                "detected_problem"
            ]

            if actual_problem == expected_problem:

                status = "PASS"
                passed_tests += 1

            else:

                status = "FAIL"
                failed_tests += 1

            print(
                f"STATUS            : {status}"
            )

            print(
                f"Expected Problem  : "
                f"{expected_problem}"
            )

            print(
                f"Actual Problem    : "
                f"{actual_problem}"
            )

            print(
                f"Confidence        : "
                f"{result['confidence']}"
            )

            print(
                f"Severity          : "
                f"{result['severity']}"
            )

            print(
                f"Safe To Drive     : "
                f"{result['safe_to_drive']}"
            )

            print(
                f"Matched Keywords  : "
                f"{result['matched_keywords']}"
            )

            print(
                f"Visual Findings   : "
                f"{result['visual_findings']}"
            )

            print(
                "Recommended Action:"
            )

            print(
                f"  {result['recommended_action']}"
            )

        except Exception as error:

            failed_tests += 1

            print(
                "STATUS            : FAIL"
            )

            print(
                f"ERROR             : {error}"
            )

    # =========================================================
    # FINAL RESULTS
    # =========================================================

    total_tests = len(test_cases)

    print()
    print("=" * 75)
    print("RSA AI VEHICLE VISION ENGINE TEST RESULTS")
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
            "RSA VEHICLE VISION ENGINE "
            "IS WORKING CORRECTLY"
        )

    else:

        print("SOME TESTS FAILED")

    print("=" * 75)