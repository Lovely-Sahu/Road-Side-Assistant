"""
TF-IDF + Logistic Regression / Random Forest incident models and the hybrid
(rules + ML) decision in the analyzer.
"""
import importlib.util
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

HAS_SKLEARN = importlib.util.find_spec("sklearn") is not None

from ai.incident_analyzer import IncidentAnalyzer  # noqa: E402


@unittest.skipUnless(HAS_SKLEARN, "scikit-learn not installed")
class IncidentModelTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        from ml.incident_models import get_incident_models
        cls.models = get_incident_models()
        assert cls.models.ensure_loaded(), cls.models.reason

    def test_both_models_predict_clear_examples(self):
        for text, label in (("my tyre is flat", "tyre_puncture"), ("the car ran out of petrol", "fuel_problem"),
                            ("battery is dead, need a jump start", "battery_failure"),
                            ("a truck crashed into my car", "accident")):
            pred = self.models.predict(text)
            self.assertTrue(pred["available"])
            self.assertEqual(pred["logistic_regression"]["problem"], label, text)
            self.assertEqual(pred["random_forest"]["problem"], label, text)

    def test_prediction_is_explained(self):
        pred = self.models.predict("smoke and steam from the bonnet, temperature very high")
        lr = pred["logistic_regression"]
        self.assertAlmostEqual(sum(lr["probabilities"].values()), 1.0, places=2)
        self.assertTrue(0 < lr["probability"] <= 1)
        self.assertTrue(lr["top_words"], "the words behind the decision are listed")
        self.assertIn("fusion", pred)

    def test_out_of_scope_problem_stays_unknown(self):
        r = IncidentAnalyzer().analyze("The AC is not cooling and the car door lock is jammed")
        self.assertEqual(r["problem"], "unknown")
        self.assertEqual(r["ml"]["logistic_regression"]["problem"], "other")


@unittest.skipUnless(HAS_SKLEARN, "scikit-learn not installed")
class HybridDecisionTests(unittest.TestCase):

    def setUp(self):
        self.hybrid = IncidentAnalyzer(use_ml=True)
        self.rules = IncidentAnalyzer(use_ml=False)

    def test_ml_fills_in_when_rules_find_nothing(self):
        text = "Tyre got puncher on the way"  # misspelt; the rule vocabulary misses it
        self.assertEqual(self.rules.analyze(text)["problem"], "unknown")
        r = self.hybrid.analyze(text)
        self.assertEqual(r["problem"], "tyre_puncture")
        self.assertEqual(r["decision_source"], "ml")
        self.assertEqual(r["evidence_source"], "ml")
        self.assertIn("Logistic Regression", r["confidence_basis"])
        self.assertTrue(r["follow_up_questions"], "an ML-only decision still asks the driver to confirm")

    def test_clear_rule_decisions_are_unchanged(self):
        for text in ("smoke is coming out of my engine", "my brakes failed", "flat tyre on the highway",
                     "battery is dead", "I ran out of petrol", "a bus hit my car"):
            self.assertEqual(self.hybrid.analyze(text)["problem"], self.rules.analyze(text)["problem"], text)
            self.assertEqual(self.hybrid.analyze(text)["decision_source"], "rules", text)

    def test_ml_never_removes_hazards_or_lowers_severity(self):
        for text in ("there are flames and smoke everywhere", "my friend is bleeding after the crash",
                     "I can smell petrol near the car"):
            h, r = self.hybrid.analyze(text), self.rules.analyze(text)
            self.assertEqual([x["hazard"] for x in h["hazards"]], [x["hazard"] for x in r["hazards"]], text)
            self.assertEqual(h["severity"], "CRITICAL", text)
            self.assertFalse(h["safe_to_drive"], text)

    def test_fuel_smell_is_never_sent_fuel_delivery(self):
        r = self.hybrid.analyze("I can smell petrol near the car")
        self.assertNotEqual(r["problem"], "fuel_problem")

    def test_accident_and_brake_decisions_are_never_replaced(self):
        r = self.hybrid.analyze("Brake lights are not working")
        self.assertEqual(r["problem"], "brake_failure", "safety first: the rules' brake decision is kept")

    def test_driver_override_still_wins(self):
        r = self.hybrid.analyze("Tyre got puncher on the way", problem_override="battery_failure")
        self.assertEqual(r["problem"], "battery_failure")
        self.assertTrue(r["driver_corrected"])
        self.assertEqual(r["ai_problem"], "tyre_puncture")

    def test_too_short_input_never_uses_ml(self):
        r = self.hybrid.analyze("abc")
        self.assertIsNone(r["ml"])
        self.assertEqual(r["problem"], "unknown")


class FallbackTests(unittest.TestCase):

    def test_rules_only_when_ml_disabled(self):
        os.environ["RSA_ML_ENABLED"] = "0"
        try:
            r = IncidentAnalyzer().analyze("smoke is coming out of my engine")
        finally:
            os.environ.pop("RSA_ML_ENABLED", None)
        self.assertEqual(r["problem"], "engine_overheating")
        self.assertEqual(r["decision_source"], "rules")
        self.assertIsNone(r["ml"])

    def test_missing_models_fall_back_to_rules(self):
        from ml.incident_models import IncidentModels
        empty = Path(tempfile.mkdtemp())
        try:
            models = IncidentModels(model_dir=empty, train_csv=empty / "missing.csv")
            r = IncidentAnalyzer(use_ml=True, ml_models=models).analyze("Tyre got puncher on the way")
            self.assertFalse(r["ml"]["available"])
            self.assertEqual(r["problem"], "unknown")
            self.assertEqual(r["decision_source"], "none")
        finally:
            shutil.rmtree(empty)

    @unittest.skipUnless(HAS_SKLEARN, "scikit-learn not installed")
    def test_models_are_retrained_when_saved_by_another_version(self):
        from ml.incident_models import IncidentModels, TRAIN_CSV
        tmp = Path(tempfile.mkdtemp())
        try:
            (tmp / "incident_models_meta.json").write_text(json.dumps({"sklearn_version": "0.0-old"}))
            models = IncidentModels(model_dir=tmp, train_csv=TRAIN_CSV)
            self.assertTrue(models.ensure_loaded())
            self.assertTrue((tmp / "incident_tfidf_logreg.joblib").exists())
            self.assertNotEqual(json.loads((tmp / "incident_models_meta.json").read_text())["sklearn_version"], "0.0-old")
        finally:
            shutil.rmtree(tmp)


@unittest.skipUnless(HAS_SKLEARN, "scikit-learn not installed")
class WebAnalyzeTests(unittest.TestCase):

    def test_analyze_api_returns_ml_check_and_request_stores_it(self):
        from tests import support
        from database.database import fetch_one
        support.fresh_database()
        driver = support.make_user("ML Driver", "ml.driver@example.test")
        support.make_provider("Tyre Pro", "Tyre Service", 20.2961, 85.8245, 4.5)
        client = support.web_client(driver)
        body = support.post(client, "/api/analyze", {"description": "Tyre got puncher on the way"}).get_json()
        self.assertTrue(body["analysis"]["ml"]["available"])
        self.assertEqual(body["analysis"]["problem"], "tyre_puncture")
        created = support.post(client, "/api/assistance/create", {"description": "Tyre got puncher on the way",
                                                                  "latitude": "20.2961", "longitude": "85.8245"})
        self.assertEqual(created.status_code, 200, created.get_json())
        rid = created.get_json()["request_id"]
        row = fetch_one("SELECT explanation FROM diagnosis_records WHERE request_id = ?", (rid,))
        details = json.loads(row["explanation"])
        self.assertEqual(details["decision_source"], "ml")
        self.assertEqual(details["ml"]["logistic_regression"]["problem"], "tyre_puncture")
        view = client.get(f"/api/tracking/{rid}").get_json()
        self.assertEqual(view["diagnosis"]["details"]["decision_source"], "ml")


if __name__ == "__main__":
    unittest.main()
