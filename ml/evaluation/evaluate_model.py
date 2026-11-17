"""
RSA ML Model Evaluation
-----------------------

Evaluates the trained RSA roadside problem classifier
using a fixed validation dataset.
"""

from pathlib import Path
import json
from collections import Counter

from ml.training.train_model import (
    DEFAULT_TRAINING_DATA,
    load_model,
)


# ==========================================================
# PATH
# ==========================================================

BASE_DIR = Path(__file__).resolve().parent
MODEL_FILE = BASE_DIR.parent / "models" / "problem_classifier_model.json"


# ==========================================================
# PREDICTION
# ==========================================================

def predict_with_model(model, text):
    """
    Predict a category using the saved word-frequency model.
    """

    if not isinstance(model, dict):
        return "OTHER"

    if not isinstance(text, str) or not text.strip():
        return "OTHER"

    words = text.lower().split()

    classes = model.get("classes", [])
    word_counts = model.get("word_counts", {})

    scores = Counter()

    for category in classes:

        category_words = word_counts.get(
            category,
            {}
        )

        for word in words:
            word = (
                word.lower()
                .replace(".", "")
                .replace(",", "")
                .replace("!", "")
                .replace("?", "")
            )

            if word in category_words:
                scores[category] += category_words[word]

    if not scores:
        return "OTHER"

    return scores.most_common(1)[0][0]


# ==========================================================
# EVALUATE
# ==========================================================

def evaluate_model(model, validation_data=None):
    """
    Evaluate the trained model.

    Returns accuracy and prediction details.
    """

    if validation_data is None:
        validation_data = DEFAULT_TRAINING_DATA

    if not isinstance(validation_data, list):
        return {
            "success": False,
            "message": "Validation data must be a list.",
        }

    if not validation_data:
        return {
            "success": False,
            "message": "Validation data cannot be empty.",
        }

    predictions = []
    correct = 0
    total = 0

    confusion_matrix = Counter()

    for item in validation_data:

        if not isinstance(item, (tuple, list)):
            continue

        if len(item) != 2:
            continue

        expected, text = item

        if not isinstance(expected, str):
            continue

        expected = expected.strip().upper()

        prediction = predict_with_model(
            model,
            text
        )

        total += 1

        if prediction == expected:
            correct += 1

        confusion_matrix[
            (expected, prediction)
        ] += 1

        predictions.append({
            "text": text,
            "expected": expected,
            "predicted": prediction,
            "correct": prediction == expected,
        })

    if total == 0:
        return {
            "success": False,
            "message": "No valid validation records found.",
        }

    accuracy = correct / total

    return {
        "success": True,
        "message": "Model evaluation completed.",
        "accuracy": round(accuracy, 4),
        "correct": correct,
        "total": total,
        "predictions": predictions,
        "confusion_matrix": {
            f"{expected}->{predicted}": count
            for (expected, predicted), count
            in confusion_matrix.items()
        },
    }


# ==========================================================
# EVALUATION REPORT
# ==========================================================

def create_evaluation_report(result):
    """
    Create a clean evaluation report.
    """

    if not isinstance(result, dict):
        return {
            "success": False,
            "message": "Invalid evaluation result.",
        }

    if not result.get("success"):
        return result

    accuracy = result.get("accuracy", 0)

    return {
        "success": True,
        "accuracy": accuracy,
        "accuracy_percentage": round(
            accuracy * 100,
            2
        ),
        "correct_predictions": result.get(
            "correct",
            0
        ),
        "total_predictions": result.get(
            "total",
            0
        ),
        "status": (
            "GOOD"
            if accuracy >= 0.80
            else "NEEDS_IMPROVEMENT"
        ),
    }


# ==========================================================
# SAVE REPORT
# ==========================================================

def save_evaluation_report(
    report,
    filename="evaluation_report.json"
):
    """
    Save evaluation report as JSON.
    """

    path = BASE_DIR / filename

    try:

        with path.open(
            "w",
            encoding="utf-8"
        ) as file:

            json.dump(
                report,
                file,
                indent=4
            )

        return {
            "success": True,
            "message": "Evaluation report saved.",
            "path": str(path),
        }

    except OSError as error:

        return {
            "success": False,
            "message": f"Unable to save report: {error}",
        }


# ==========================================================
# TEST
# ==========================================================

if __name__ == "__main__":

    print("=" * 60)
    print("RSA ML MODEL EVALUATION TEST")
    print("=" * 60)

    # ------------------------------------------------------
    # Load model
    # ------------------------------------------------------

    loaded = load_model(MODEL_FILE)

    print(
        "Model loading       :",
        "PASS"
        if loaded["success"]
        else "FAIL"
    )

    if loaded["success"]:

        model = loaded["model"]

        # --------------------------------------------------
        # Evaluate
        # --------------------------------------------------

        evaluation = evaluate_model(
            model
        )

        print(
            "Model evaluation    :",
            "PASS"
            if evaluation["success"]
            else "FAIL"
        )

        if evaluation["success"]:

            print(
                "Accuracy            :",
                f"{evaluation['accuracy'] * 100:.2f}%"
            )

            print(
                "Correct predictions :",
                evaluation["correct"]
            )

            print(
                "Total predictions   :",
                evaluation["total"]
            )

            # --------------------------------------------------
            # Report
            # --------------------------------------------------

            report = create_evaluation_report(
                evaluation
            )

            print(
                "Report generation   :",
                "PASS"
                if report["success"]
                else "FAIL"
            )

            # --------------------------------------------------
            # Save report
            # --------------------------------------------------

            saved = save_evaluation_report(
                report
            )

            print(
                "Report saving       :",
                "PASS"
                if saved["success"]
                else "FAIL"
            )

    print("=" * 60)
    print("RSA ML MODEL EVALUATION TEST COMPLETE")
    print("=" * 60)