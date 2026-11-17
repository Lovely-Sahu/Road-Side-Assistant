# ============================================================
# RSA - AI PREDICTION ENGINE
# ============================================================

class PredictionEngine:

    # ---------------------------------------------------------
    # INITIALIZATION
    # ---------------------------------------------------------

    def __init__(self):

        self.prediction_rules = {

            "engine_overheating": {
                "risk": "HIGH",
                "prediction":
                    "The vehicle may experience engine damage or breakdown if overheating continues.",
                "preventive_action":
                    "Stop the vehicle safely, switch off the engine, and allow it to cool before professional inspection."
            },

            "brake_failure": {
                "risk": "CRITICAL",
                "prediction":
                    "The vehicle may be unable to stop safely and could be involved in a serious accident.",
                "preventive_action":
                    "Do not continue driving. Request emergency roadside assistance immediately."
            },

            "tyre_puncture": {
                "risk": "HIGH",
                "prediction":
                    "The damaged tyre may lose further pressure and affect vehicle stability.",
                "preventive_action":
                    "Reduce speed safely, stop at a safe location, and request tyre assistance."
            },

            "battery_failure": {
                "risk": "MEDIUM",
                "prediction":
                    "The vehicle may fail to start or may lose electrical power.",
                "preventive_action":
                    "Request battery assistance and have the battery and charging system inspected."
            },

            "engine_failure": {
                "risk": "HIGH",
                "prediction":
                    "The vehicle may remain immobilized and may require mechanical repair.",
                "preventive_action":
                    "Move to a safe location if possible and request roadside assistance."
            },

            "accident": {
                "risk": "CRITICAL",
                "prediction":
                    "The vehicle may have safety-related damage that requires immediate inspection.",
                "preventive_action":
                    "Check for injuries, move to safety if possible, and contact emergency services."
            },

            "fuel_problem": {
                "risk": "MEDIUM",
                "prediction":
                    "The vehicle will remain immobilized until an adequate fuel supply is restored.",
                "preventive_action":
                    "Move to a safe location and request fuel delivery or roadside assistance."
            },

            "electrical_failure": {
                "risk": "MEDIUM",
                "prediction":
                    "Electrical functions may continue to malfunction and could affect vehicle operation.",
                "preventive_action":
                    "Stop safely and request professional electrical inspection."
            },

            "unknown": {
                "risk": "LOW",
                "prediction":
                    "The available information is insufficient to predict a specific vehicle failure.",
                "preventive_action":
                    "Monitor the vehicle carefully and arrange professional diagnosis if the problem continues."
            }
        }

    # ---------------------------------------------------------
    # PREDICT RISK
    # ---------------------------------------------------------

    def predict_risk(
        self,
        problem,
        severity,
        safe_to_drive
    ):

        # Critical severity always produces critical prediction risk
        if severity == "CRITICAL":

            return "CRITICAL"

        # Unsafe vehicles should not receive a low prediction risk
        if not safe_to_drive and severity == "HIGH":

            return "HIGH"

        if problem in self.prediction_rules:

            return self.prediction_rules[problem]["risk"]

        if severity == "HIGH":

            return "HIGH"

        if severity == "MEDIUM":

            return "MEDIUM"

        return "LOW"

    # ---------------------------------------------------------
    # PREDICT FUTURE CONDITION
    # ---------------------------------------------------------

    def predict_condition(
        self,
        problem,
        severity,
        safe_to_drive
    ):

        rule = self.prediction_rules.get(
            problem,
            self.prediction_rules["unknown"]
        )

        prediction = rule["prediction"]

        # Add additional warning for unsafe vehicles
        if not safe_to_drive:

            prediction += (
                " Continuing to drive may increase the risk "
                "of further damage or an unsafe situation."
            )

        return prediction

    # ---------------------------------------------------------
    # PREVENTIVE ACTION
    # ---------------------------------------------------------

    def get_preventive_action(
        self,
        problem,
        severity,
        safe_to_drive
    ):

        rule = self.prediction_rules.get(
            problem,
            self.prediction_rules["unknown"]
        )

        return rule["preventive_action"]

    # ---------------------------------------------------------
    # CONFIDENCE
    # ---------------------------------------------------------

    def calculate_prediction_confidence(
        self,
        problem,
        diagnostic_confidence=0.0
    ):

        try:

            diagnostic_confidence = float(
                diagnostic_confidence
            )

        except (TypeError, ValueError):

            diagnostic_confidence = 0.0

        diagnostic_confidence = max(
            0.0,
            min(diagnostic_confidence, 1.0)
        )

        if problem == "unknown":

            return round(
                diagnostic_confidence * 0.50,
                2
            )

        # Prediction confidence is based mainly on
        # the diagnostic confidence.
        confidence = (
            0.70 * diagnostic_confidence
            + 0.30
        )

        return round(
            min(confidence, 0.99),
            2
        )

    # ---------------------------------------------------------
    # COMPLETE PREDICTION
    # ---------------------------------------------------------

    def predict(
        self,
        problem,
        severity,
        safe_to_drive,
        diagnostic_confidence=0.0
    ):

        prediction_risk = self.predict_risk(
            problem,
            severity,
            safe_to_drive
        )

        predicted_condition = self.predict_condition(
            problem,
            severity,
            safe_to_drive
        )

        preventive_action = self.get_preventive_action(
            problem,
            severity,
            safe_to_drive
        )

        prediction_confidence = (
            self.calculate_prediction_confidence(
                problem,
                diagnostic_confidence
            )
        )

        return {

            "prediction_risk":
                prediction_risk,

            "predicted_condition":
                predicted_condition,

            "preventive_action":
                preventive_action,

            "prediction_confidence":
                prediction_confidence
        }


# ============================================================
# TEST SUITE
# ============================================================

if __name__ == "__main__":

    engine = PredictionEngine()

    test_cases = [

        {
            "name": "ENGINE OVERHEATING",
            "problem": "engine_overheating",
            "severity": "CRITICAL",
            "safe_to_drive": False,
            "diagnostic_confidence": 0.87,
            "expected_risk": "CRITICAL"
        },

        {
            "name": "BRAKE FAILURE",
            "problem": "brake_failure",
            "severity": "CRITICAL",
            "safe_to_drive": False,
            "diagnostic_confidence": 0.91,
            "expected_risk": "CRITICAL"
        },

        {
            "name": "TYRE PUNCTURE",
            "problem": "tyre_puncture",
            "severity": "HIGH",
            "safe_to_drive": False,
            "diagnostic_confidence": 0.82,
            "expected_risk": "HIGH"
        },

        {
            "name": "BATTERY FAILURE",
            "problem": "battery_failure",
            "severity": "MEDIUM",
            "safe_to_drive": True,
            "diagnostic_confidence": 0.84,
            "expected_risk": "MEDIUM"
        },

        {
            "name": "ACCIDENT",
            "problem": "accident",
            "severity": "CRITICAL",
            "safe_to_drive": False,
            "diagnostic_confidence": 0.90,
            "expected_risk": "CRITICAL"
        },

        {
            "name": "FUEL PROBLEM",
            "problem": "fuel_problem",
            "severity": "MEDIUM",
            "safe_to_drive": True,
            "diagnostic_confidence": 0.80,
            "expected_risk": "MEDIUM"
        },

        {
            "name": "ELECTRICAL FAILURE",
            "problem": "electrical_failure",
            "severity": "MEDIUM",
            "safe_to_drive": True,
            "diagnostic_confidence": 0.81,
            "expected_risk": "MEDIUM"
        },

        {
            "name": "ENGINE FAILURE",
            "problem": "engine_failure",
            "severity": "HIGH",
            "safe_to_drive": False,
            "diagnostic_confidence": 0.78,
            "expected_risk": "HIGH"
        },

        {
            "name": "UNKNOWN",
            "problem": "unknown",
            "severity": "LOW",
            "safe_to_drive": True,
            "diagnostic_confidence": 0.0,
            "expected_risk": "LOW"
        }
    ]

    print()
    print("=" * 75)
    print("RSA AI PREDICTION ENGINE - TEST SUITE")
    print("=" * 75)

    passed_tests = 0
    failed_tests = 0

    for test in test_cases:

        print()
        print("-" * 75)

        print(
            f"TEST              : "
            f"{test['name']}"
        )

        print(
            f"Expected Risk     : "
            f"{test['expected_risk']}"
        )

        try:

            result = engine.predict(
                problem=test["problem"],
                severity=test["severity"],
                safe_to_drive=test["safe_to_drive"],
                diagnostic_confidence=
                    test["diagnostic_confidence"]
            )

            risk_match = (
                result["prediction_risk"]
                == test["expected_risk"]
            )

            condition_valid = (
                isinstance(
                    result["predicted_condition"],
                    str
                )
                and len(
                    result["predicted_condition"].strip()
                ) > 0
            )

            action_valid = (
                isinstance(
                    result["preventive_action"],
                    str
                )
                and len(
                    result["preventive_action"].strip()
                ) > 0
            )

            confidence_valid = (
                isinstance(
                    result["prediction_confidence"],
                    (int, float)
                )
                and 0.0 <=
                    result["prediction_confidence"]
                    <= 1.0
            )

            if (
                risk_match
                and condition_valid
                and action_valid
                and confidence_valid
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
                f"Actual Risk       : "
                f"{result['prediction_risk']}"
            )

            print(
                f"Prediction Confidence: "
                f"{result['prediction_confidence']}"
            )

            print(
                "Predicted Condition:"
            )

            print(
                f"  {result['predicted_condition']}"
            )

            print(
                "Preventive Action:"
            )

            print(
                f"  {result['preventive_action']}"
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
    print("RSA AI PREDICTION ENGINE TEST RESULTS")
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
        print(
            "RSA PREDICTION ENGINE "
            "IS WORKING CORRECTLY"
        )

    else:

        print("SOME TESTS FAILED")

    print("=" * 75)