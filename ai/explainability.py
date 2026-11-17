# ============================================================
# RSA - AI EXPLAINABILITY ENGINE
# ============================================================

class ExplainabilityEngine:

    # ---------------------------------------------------------
    # INITIALIZATION
    # ---------------------------------------------------------

    def __init__(self):

        self.problem_descriptions = {

            "engine_overheating":
                "The vehicle shows signs of engine overheating.",

            "brake_failure":
                "The braking system appears to have failed or is not functioning correctly.",

            "tyre_puncture":
                "The vehicle appears to have a punctured or flat tyre.",

            "battery_failure":
                "The vehicle appears to have a battery or starting-system problem.",

            "engine_failure":
                "The engine appears to have stopped or failed.",

            "accident":
                "The incident indicates that the vehicle has been involved in an accident or collision.",

            "fuel_problem":
                "The vehicle appears to have a fuel-related problem.",

            "electrical_failure":
                "The vehicle appears to have an electrical-system problem.",

            "unknown":
                "No specific vehicle problem could be identified from the provided information."
        }

        self.severity_explanations = {

            "CRITICAL":
                "The incident is classified as critical because it may create an immediate safety risk.",

            "HIGH":
                "The incident is classified as high severity and should be handled urgently.",

            "MEDIUM":
                "The incident is classified as medium severity and requires attention.",

            "LOW":
                "The incident appears to be low risk based on the available information."
        }

        self.priority_explanations = {

            "EMERGENCY":
                "Emergency priority was assigned because immediate assistance may be required.",

            "URGENT":
                "Urgent priority was assigned because the vehicle should not continue normal operation.",

            "NORMAL":
                "Normal priority was assigned because roadside assistance is recommended but there is no immediate emergency escalation.",

            "LOW":
                "Low priority was assigned because no immediate serious risk was identified."
        }

    # ---------------------------------------------------------
    # PROBLEM EXPLANATION
    # ---------------------------------------------------------

    def explain_problem(
        self,
        problem,
        matched_keywords=None
    ):

        explanation = self.problem_descriptions.get(
            problem,
            self.problem_descriptions["unknown"]
        )

        if matched_keywords:

            keywords = ", ".join(
                str(keyword)
                for keyword in matched_keywords
            )

            explanation += (
                f" Detected indicators: {keywords}."
            )

        return explanation

    # ---------------------------------------------------------
    # CONFIDENCE EXPLANATION
    # ---------------------------------------------------------

    def explain_confidence(self, confidence):

        if confidence >= 0.80:

            return (
                "The AI has high confidence in this diagnosis "
                "because multiple relevant indicators were detected."
            )

        if confidence >= 0.60:

            return (
                "The AI has moderate confidence in this diagnosis "
                "because relevant indicators were detected."
            )

        if confidence > 0:

            return (
                "The AI has limited confidence because only "
                "a small number of relevant indicators were detected."
            )

        return (
            "The AI could not identify sufficient indicators "
            "to determine a specific vehicle problem."
        )

    # ---------------------------------------------------------
    # SEVERITY EXPLANATION
    # ---------------------------------------------------------

    def explain_severity(self, severity):

        return self.severity_explanations.get(
            severity,
            "Severity could not be determined."
        )

    # ---------------------------------------------------------
    # SAFETY EXPLANATION
    # ---------------------------------------------------------

    def explain_safety(
        self,
        safe_to_drive,
        problem,
        severity
    ):

        if not safe_to_drive:

            if severity == "CRITICAL":

                return (
                    "The vehicle should not be driven because "
                    "the incident has been classified as critical."
                )

            if problem in [
                "brake_failure",
                "engine_overheating",
                "engine_failure",
                "tyre_puncture"
            ]:

                return (
                    "The vehicle should not continue normal driving "
                    "because the detected problem may affect vehicle safety."
                )

            return (
                "The vehicle is not considered safe to drive "
                "until the problem is assessed."
            )

        return (
            "The vehicle is currently considered safe to drive "
            "based on the available incident information, "
            "but professional inspection may still be required."
        )

    # ---------------------------------------------------------
    # PRIORITY EXPLANATION
    # ---------------------------------------------------------

    def explain_priority(self, priority):

        return self.priority_explanations.get(
            priority,
            "Priority could not be determined."
        )

    # ---------------------------------------------------------
    # ESCALATION EXPLANATION
    # ---------------------------------------------------------

    def explain_escalation(self, escalation):

        if escalation:

            return (
                "The case is escalated because it requires "
                "emergency-level assistance."
            )

        return (
            "The case does not require emergency escalation "
            "based on the current assessment."
        )

    # ---------------------------------------------------------
    # SERVICE EXPLANATION
    # ---------------------------------------------------------

    def explain_service(
        self,
        service
    ):

        service_explanations = {

            "emergency_roadside_assistance":
                "Emergency roadside assistance is recommended because the vehicle may present an immediate safety risk.",

            "emergency_services":
                "Emergency services are recommended because the incident involves an accident or collision.",

            "mechanic_or_roadside_assistance":
                "A mechanic or roadside assistance provider is recommended to inspect and repair the vehicle.",

            "tyre_assistance":
                "Tyre assistance is recommended to inspect, repair, or replace the damaged tyre.",

            "battery_assistance":
                "Battery assistance is recommended for jump-starting or inspecting the vehicle battery.",

            "fuel_delivery":
                "Fuel delivery is recommended because the vehicle has a fuel-related problem.",

            "electrical_vehicle_assistance":
                "Electrical vehicle assistance is recommended to inspect the vehicle's electrical system.",

            "general_roadside_assistance":
                "General roadside assistance is recommended for further diagnosis."
        }

        return service_explanations.get(
            service,
            "Professional roadside assistance is recommended."
        )

    # ---------------------------------------------------------
    # COMPLETE EXPLANATION
    # ---------------------------------------------------------

    def explain(
        self,
        problem,
        confidence,
        severity,
        safe_to_drive,
        priority,
        service,
        escalation,
        matched_keywords=None
    ):

        problem_explanation = self.explain_problem(
            problem,
            matched_keywords
        )

        confidence_explanation = self.explain_confidence(
            confidence
        )

        severity_explanation = self.explain_severity(
            severity
        )

        safety_explanation = self.explain_safety(
            safe_to_drive,
            problem,
            severity
        )

        priority_explanation = self.explain_priority(
            priority
        )

        escalation_explanation = self.explain_escalation(
            escalation
        )

        service_explanation = self.explain_service(
            service
        )

        return {

            "problem_explanation":
                problem_explanation,

            "confidence_explanation":
                confidence_explanation,

            "severity_explanation":
                severity_explanation,

            "safety_explanation":
                safety_explanation,

            "priority_explanation":
                priority_explanation,

            "escalation_explanation":
                escalation_explanation,

            "service_explanation":
                service_explanation
        }


# ============================================================
# TEST SUITE
# ============================================================

if __name__ == "__main__":

    engine = ExplainabilityEngine()

    test_cases = [

        {
            "name": "ENGINE OVERHEATING",
            "problem": "engine_overheating",
            "confidence": 0.87,
            "severity": "CRITICAL",
            "safe_to_drive": False,
            "priority": "EMERGENCY",
            "service": "mechanic_or_roadside_assistance",
            "escalation": True,
            "matched_keywords": [
                "engine is very hot",
                "smoke coming from the engine"
            ]
        },

        {
            "name": "BRAKE FAILURE",
            "problem": "brake_failure",
            "confidence": 0.91,
            "severity": "CRITICAL",
            "safe_to_drive": False,
            "priority": "EMERGENCY",
            "service": "emergency_roadside_assistance",
            "escalation": True,
            "matched_keywords": [
                "brakes have completely failed",
                "car won't stop"
            ]
        },

        {
            "name": "TYRE PUNCTURE",
            "problem": "tyre_puncture",
            "confidence": 0.82,
            "severity": "HIGH",
            "safe_to_drive": False,
            "priority": "URGENT",
            "service": "tyre_assistance",
            "escalation": False,
            "matched_keywords": [
                "flat tyre"
            ]
        },

        {
            "name": "BATTERY FAILURE",
            "problem": "battery_failure",
            "confidence": 0.84,
            "severity": "MEDIUM",
            "safe_to_drive": True,
            "priority": "NORMAL",
            "service": "battery_assistance",
            "escalation": False,
            "matched_keywords": [
                "battery is dead",
                "car won't start"
            ]
        },

        {
            "name": "ACCIDENT",
            "problem": "accident",
            "confidence": 0.90,
            "severity": "CRITICAL",
            "safe_to_drive": False,
            "priority": "EMERGENCY",
            "service": "emergency_services",
            "escalation": True,
            "matched_keywords": [
                "collision"
            ]
        },

        {
            "name": "FUEL PROBLEM",
            "problem": "fuel_problem",
            "confidence": 0.80,
            "severity": "MEDIUM",
            "safe_to_drive": True,
            "priority": "NORMAL",
            "service": "fuel_delivery",
            "escalation": False,
            "matched_keywords": [
                "out of fuel"
            ]
        },

        {
            "name": "ELECTRICAL FAILURE",
            "problem": "electrical_failure",
            "confidence": 0.81,
            "severity": "MEDIUM",
            "safe_to_drive": True,
            "priority": "NORMAL",
            "service": "electrical_vehicle_assistance",
            "escalation": False,
            "matched_keywords": [
                "dashboard went blank"
            ]
        },

        {
            "name": "ENGINE FAILURE",
            "problem": "engine_failure",
            "confidence": 0.78,
            "severity": "HIGH",
            "safe_to_drive": False,
            "priority": "URGENT",
            "service": "mechanic_or_roadside_assistance",
            "escalation": False,
            "matched_keywords": [
                "engine suddenly stopped"
            ]
        },

        {
            "name": "UNKNOWN",
            "problem": "unknown",
            "confidence": 0.0,
            "severity": "LOW",
            "safe_to_drive": True,
            "priority": "LOW",
            "service": "general_roadside_assistance",
            "escalation": False,
            "matched_keywords": []
        }
    ]

    print()
    print("=" * 75)
    print("RSA AI EXPLAINABILITY ENGINE - TEST SUITE")
    print("=" * 75)

    passed_tests = 0
    failed_tests = 0

    for test in test_cases:

        print()
        print("-" * 75)
        print(f"TEST              : {test['name']}")

        try:

            result = engine.explain(
                problem=test["problem"],
                confidence=test["confidence"],
                severity=test["severity"],
                safe_to_drive=test["safe_to_drive"],
                priority=test["priority"],
                service=test["service"],
                escalation=test["escalation"],
                matched_keywords=test["matched_keywords"]
            )

            required_fields = [
                "problem_explanation",
                "confidence_explanation",
                "severity_explanation",
                "safety_explanation",
                "priority_explanation",
                "escalation_explanation",
                "service_explanation"
            ]

            valid = all(
                field in result
                and isinstance(result[field], str)
                and len(result[field].strip()) > 0
                for field in required_fields
            )

            if valid:

                print("STATUS            : PASS")
                passed_tests += 1

            else:

                print("STATUS            : FAIL")
                failed_tests += 1

            print()
            print("Problem Explanation:")
            print(f"  {result['problem_explanation']}")

            print()
            print("Confidence Explanation:")
            print(f"  {result['confidence_explanation']}")

            print()
            print("Severity Explanation:")
            print(f"  {result['severity_explanation']}")

            print()
            print("Safety Explanation:")
            print(f"  {result['safety_explanation']}")

            print()
            print("Priority Explanation:")
            print(f"  {result['priority_explanation']}")

            print()
            print("Escalation Explanation:")
            print(f"  {result['escalation_explanation']}")

            print()
            print("Service Explanation:")
            print(f"  {result['service_explanation']}")

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
    print("RSA AI EXPLAINABILITY ENGINE TEST RESULTS")
    print("=" * 75)

    print(f"TOTAL TESTS       : {total_tests}")
    print(f"PASSED            : {passed_tests}")
    print(f"FAILED            : {failed_tests}")

    print("=" * 75)

    if failed_tests == 0:

        print("ALL TESTS PASSED")
        print("RSA EXPLAINABILITY ENGINE IS WORKING CORRECTLY")

    else:

        print("SOME TESTS FAILED")

    print("=" * 75)