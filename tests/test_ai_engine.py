"""AI engine validation: normal, ambiguous, incomplete, unsupported and high-risk descriptions."""
import unittest

from tests import support  # noqa: F401  (sets the isolated environment)
from ai.diagnosis import DiagnosisEngine
from ai.incident_analyzer import IncidentAnalyzer, SUPPORTED_PROBLEMS
from ai.vehicle_health import VehicleHealthEngine
from assistance.matching import AssistanceMatcher


class IncidentAnalyzerTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.ai = IncidentAnalyzer()

    def analyze(self, text, **kw):
        return self.ai.analyze(text, **kw)

    # ---- supported incidents ---------------------------------------------
    def test_engine_overheating(self):
        r = self.analyze("The engine temperature warning is on and the engine is overheating")
        self.assertEqual(r["problem"], "engine_overheating")
        self.assertFalse(r["safe_to_drive"])
        self.assertIn(r["severity"], ("HIGH", "CRITICAL"))

    def test_brake_failure(self):
        r = self.analyze("My brakes are not working and the car won't stop")
        self.assertEqual(r["problem"], "brake_failure")
        self.assertEqual(r["severity"], "CRITICAL")
        self.assertFalse(r["safe_to_drive"])

    def test_brake_failure_free_wording(self):
        r = self.analyze("I pressed the brake pedal and it goes to the floor, brakes feel spongy")
        self.assertEqual(r["problem"], "brake_failure")
        self.assertEqual(r["severity"], "CRITICAL")

    def test_tyre_puncture(self):
        for text in ("I have a flat tyre", "rear left tire went flat on the highway"):
            self.assertEqual(self.analyze(text)["problem"], "tyre_puncture", text)

    def test_battery(self):
        for text in ("My battery is dead and the car won't start", "battery is completely drained, it just clicks"):
            self.assertEqual(self.analyze(text)["problem"], "battery_failure", text)

    # ---- the "Unknown" incident observed in the live database (request #2) --
    def test_regression_smoke_is_coming_from_the_engine(self):
        r = self.analyze("My car was stopped and smoke is coming from the engine")
        self.assertEqual(r["problem"], "engine_overheating")
        self.assertEqual(r["severity"], "CRITICAL")
        self.assertFalse(r["safe_to_drive"])
        self.assertIn("smoke", [h["hazard"] for h in r["hazards"]])
        # Inferred from related words, so it must be reported as a weaker match.
        self.assertEqual(r["evidence_source"], "symptom_proximity")
        self.assertLessEqual(r["confidence"], 0.6)

    # ---- ambiguous / incomplete / unsupported --------------------------------
    def test_ambiguous_description_asks_follow_up(self):
        r = self.analyze("car stopped, maybe a flat tyre or the battery is dead")
        self.assertTrue(r["ambiguous"])
        self.assertTrue(r["follow_up_questions"])
        self.assertTrue(r["needs_clarification"])

    def test_empty_and_invalid_input(self):
        for value in ("", "   ", None, 12345, "abc"):
            r = self.analyze(value)
            self.assertEqual(r["problem"], "unknown")
            self.assertEqual(r["confidence"], 0.0)
            self.assertTrue(r["follow_up_questions"])
        self.assertEqual(self.analyze("")["input_quality"], "empty")

    def test_unsupported_incident_is_unknown_not_guessed(self):
        r = self.analyze("There is a strange rattling noise from the back seat")
        self.assertEqual(r["problem"], "unknown")
        self.assertEqual(r["safety_assessment"], "NOT_CONFIRMED")
        self.assertFalse(r["safe_to_drive"], "an unidentified problem must not be reported as safe")

    # ---- hazards ---------------------------------------------------------------
    def test_dangerous_symptoms_are_critical(self):
        for text, hazard in (
            ("there are flames under the bonnet", "fire"),
            ("I can smell petrol near the car", "fuel_leak"),
            ("a truck hit us and my friend is bleeding", "injury"),
        ):
            r = self.analyze(text)
            self.assertEqual(r["severity"], "CRITICAL", text)
            self.assertIn(hazard, [h["hazard"] for h in r["hazards"]], text)
            self.assertFalse(r["safe_to_drive"], text)

    def test_negated_hazard_is_not_reported(self):
        r = self.analyze("There is no smoke but the engine is very hot")
        self.assertEqual(r["problem"], "engine_overheating")
        self.assertEqual(r["hazards"], [])
        self.assertEqual(r["severity"], "HIGH")

    def test_fuel_smell_is_not_routed_to_fuel_delivery(self):
        r = self.analyze("I can smell petrol near the car")
        self.assertNotEqual(r["problem"], "fuel_problem")

    def test_accident_with_smoke_is_accident(self):
        r = self.analyze("My car crashed into a divider and smoke is coming from the engine")
        self.assertEqual(r["problem"], "accident")

    def test_hit_the_brakes_is_not_an_accident(self):
        r = self.analyze("I hit the brakes hard and now the tyre is flat")
        self.assertNotEqual(r["problem"], "accident")

    # ---- driver correction --------------------------------------------------------
    def test_driver_override_cannot_hide_hazards(self):
        r = self.analyze("smoke coming from the engine", problem_override="battery_failure")
        self.assertEqual(r["problem"], "battery_failure")
        self.assertTrue(r["driver_corrected"])
        self.assertEqual(r["ai_problem"], "engine_overheating")
        self.assertEqual(r["severity"], "CRITICAL")

    def test_invalid_override_ignored(self):
        r = self.analyze("flat tyre", problem_override="teleport_failure")
        self.assertEqual(r["problem"], "tyre_puncture")
        self.assertFalse(r["driver_corrected"])

    def test_output_is_structured_and_labelled_as_prediction(self):
        r = self.analyze("flat tyre")
        for key in ("problem", "confidence", "severity", "safe_to_drive", "recommended_action",
                    "assistance_type", "matched_keywords", "is_prediction", "confidence_basis", "hazards"):
            self.assertIn(key, r)
        self.assertTrue(r["is_prediction"])
        self.assertIn(r["problem"], SUPPORTED_PROBLEMS)


class DiagnosisAndHealthTests(unittest.TestCase):

    def test_diagnosis_is_never_confirmed_and_has_safety_steps(self):
        analysis = IncidentAnalyzer().analyze("smoke is coming out of my engine")
        d = DiagnosisEngine().diagnose(analysis["problem"], "smoke", analysis)
        self.assertFalse(d["is_confirmed"])
        self.assertTrue(d["disclaimer"])
        self.assertTrue(any("smoke" in step.lower() for step in d["safety_steps"]))
        self.assertTrue(d["recommend_towing"])
        self.assertIn("Oil leaking onto hot engine parts", d["likely_causes"])

    def test_brake_failure_recommends_towing(self):
        analysis = IncidentAnalyzer().analyze("brakes failed")
        self.assertTrue(DiagnosisEngine().diagnose("brake_failure", "brakes failed", analysis)["recommend_towing"])

    def test_injury_advises_emergency_services(self):
        analysis = IncidentAnalyzer().analyze("accident, my passenger is injured")
        d = DiagnosisEngine().diagnose(analysis["problem"], "", analysis)
        self.assertTrue(d["emergency_services_advised"])
        self.assertIn("112", d["safety_steps"][0])

    def test_health_uses_analysis_context_and_declares_no_sensor_data(self):
        text = "My car was stopped and smoke is coming from the engine"
        a = IncidentAnalyzer().analyze(text)
        h = VehicleHealthEngine().analyze(text, a["problem"], a["severity"], a["safe_to_drive"])
        self.assertFalse(h["safe_to_drive"])
        self.assertNotEqual(h["health_status"], "GOOD")
        self.assertFalse(h["sensor_data_used"])

    def test_matcher_priorities(self):
        m = AssistanceMatcher()
        self.assertEqual(m.match_assistance("brake_failure", "CRITICAL", False)["priority"], "EMERGENCY")
        self.assertEqual(m.match_assistance("engine_overheating", "CRITICAL", False)["priority"], "EMERGENCY")
        self.assertEqual(m.match_assistance("battery_failure", "MEDIUM", True)["priority"], "NORMAL")


if __name__ == "__main__":
    unittest.main()
