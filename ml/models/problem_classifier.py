"""
RSA ML Problem Classifier
--------------------------

Text-based roadside problem classification model.

The classifier predicts a roadside assistance category
from a problem description.
"""

from collections import Counter
import re


# ==========================================================
# MODEL
# ==========================================================

class ProblemClassifier:
    """
    Lightweight keyword-based problem classifier.

    This provides a deterministic baseline model that can
    later be replaced by a trained ML model.
    """

    CATEGORIES = {
        "ENGINE": {
            "engine",
            "motor",
            "starting",
            "start",
            "stall",
            "stalled",
            "power loss",
        },
        "BRAKE": {
            "brake",
            "brakes",
            "braking",
            "stop",
            "stopping",
        },
        "TYRE": {
            "tyre",
            "tire",
            "wheel",
            "puncture",
            "flat",
        },
        "BATTERY": {
            "battery",
            "dead battery",
            "jump start",
            "charging",
        },
        "ELECTRICAL": {
            "electrical",
            "electric",
            "wiring",
            "fuse",
            "light",
            "lights",
        },
        "FUEL": {
            "fuel",
            "petrol",
            "diesel",
            "empty tank",
            "out of fuel",
        },
        "OVERHEATING": {
            "overheating",
            "overheat",
            "hot engine",
            "temperature",
            "coolant",
        },
        "ACCIDENT": {
            "accident",
            "crash",
            "collision",
            "hit",
            "injury",
        },
    }

    DEFAULT_CATEGORY = "OTHER"

    def __init__(self):
        self.is_fitted = True

    # ------------------------------------------------------
    # TEXT NORMALIZATION
    # ------------------------------------------------------

    @staticmethod
    def _normalize_text(text: str) -> str:
        """
        Normalize input text.
        """

        if not isinstance(text, str):
            return ""

        text = text.lower().strip()

        text = re.sub(
            r"[^a-z0-9\s]",
            " ",
            text,
        )

        text = re.sub(
            r"\s+",
            " ",
            text,
        )

        return text

    # ------------------------------------------------------
    # PREDICT
    # ------------------------------------------------------

    def predict(self, text: str) -> str:
        """
        Predict the most likely roadside problem category.
        """

        normalized = self._normalize_text(text)

        if not normalized:
            return self.DEFAULT_CATEGORY

        scores = Counter()

        for category, keywords in self.CATEGORIES.items():

            for keyword in keywords:

                keyword = self._normalize_text(keyword)

                if not keyword:
                    continue

                if keyword in normalized:
                    scores[category] += 1

        if not scores:
            return self.DEFAULT_CATEGORY

        return scores.most_common(1)[0][0]

    # ------------------------------------------------------
    # PREDICT WITH CONFIDENCE
    # ------------------------------------------------------

    def predict_with_confidence(self, text: str):
        """
        Predict category and return a simple confidence score.
        """

        normalized = self._normalize_text(text)

        if not normalized:
            return {
                "category": self.DEFAULT_CATEGORY,
                "confidence": 0.0,
            }

        scores = Counter()

        for category, keywords in self.CATEGORIES.items():

            for keyword in keywords:

                keyword = self._normalize_text(keyword)

                if keyword in normalized:
                    scores[category] += 1

        if not scores:
            return {
                "category": self.DEFAULT_CATEGORY,
                "confidence": 0.0,
            }

        category, score = scores.most_common(1)[0]

        total_score = sum(scores.values())

        confidence = score / total_score

        return {
            "category": category,
            "confidence": round(confidence, 4),
        }

    # ------------------------------------------------------
    # BATCH PREDICTION
    # ------------------------------------------------------

    def predict_batch(self, texts):
        """
        Predict categories for multiple descriptions.
        """

        if not isinstance(texts, list):
            return []

        return [
            self.predict(text)
            for text in texts
        ]


# ==========================================================
# MODEL FACTORY
# ==========================================================

def create_problem_classifier():
    """
    Create and return a problem classifier instance.
    """

    return ProblemClassifier()


# ==========================================================
# TEST
# ==========================================================

if __name__ == "__main__":

    print("=" * 60)
    print("RSA ML PROBLEM CLASSIFIER TEST")
    print("=" * 60)

    model = create_problem_classifier()

    # ------------------------------------------------------
    # Engine
    # ------------------------------------------------------

    engine_result = model.predict(
        "My engine will not start."
    )

    print(
        "Engine classification :",
        "PASS"
        if engine_result == "ENGINE"
        else "FAIL"
    )

    # ------------------------------------------------------
    # Battery
    # ------------------------------------------------------

    battery_result = model.predict(
        "The battery is completely dead."
    )

    print(
        "Battery classification :",
        "PASS"
        if battery_result == "BATTERY"
        else "FAIL"
    )

    # ------------------------------------------------------
    # Tyre
    # ------------------------------------------------------

    tyre_result = model.predict(
        "I have a flat tyre."
    )

    print(
        "Tyre classification    :",
        "PASS"
        if tyre_result == "TYRE"
        else "FAIL"
    )

    # ------------------------------------------------------
    # Accident
    # ------------------------------------------------------

    accident_result = model.predict(
        "The vehicle was involved in an accident."
    )

    print(
        "Accident classification:",
        "PASS"
        if accident_result == "ACCIDENT"
        else "FAIL"
    )

    # ------------------------------------------------------
    # Unknown
    # ------------------------------------------------------

    unknown_result = model.predict(
        "I need some roadside help."
    )

    print(
        "Unknown classification :",
        "PASS"
        if unknown_result == "OTHER"
        else "FAIL"
    )

    # ------------------------------------------------------
    # Confidence
    # ------------------------------------------------------

    confidence_result = model.predict_with_confidence(
        "My car battery is dead."
    )

    print(
        "Confidence prediction  :",
        "PASS"
        if confidence_result["category"] == "BATTERY"
        and confidence_result["confidence"] > 0
        else "FAIL"
    )

    # ------------------------------------------------------
    # Batch
    # ------------------------------------------------------

    batch_result = model.predict_batch(
        [
            "Flat tyre",
            "Engine won't start",
            "Battery is dead",
        ]
    )

    print(
        "Batch prediction       :",
        "PASS"
        if batch_result == [
            "TYRE",
            "ENGINE",
            "BATTERY",
        ]
        else "FAIL"
    )

    print("=" * 60)
    print("RSA ML PROBLEM CLASSIFIER TEST COMPLETE")
    print("=" * 60)