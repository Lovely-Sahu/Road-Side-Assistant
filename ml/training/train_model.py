"""
RSA ML Model Training
---------------------

Training utilities for the RSA roadside problem classifier.

This module prepares training data, trains a lightweight
problem-classification model, and saves model metadata.
"""

from pathlib import Path
import json
import re
from collections import Counter


# ==========================================================
# PATHS
# ==========================================================

BASE_DIR = Path(__file__).resolve().parent
MODEL_DIR = BASE_DIR.parent / "models"
MODEL_FILE = MODEL_DIR / "problem_classifier_model.json"


# ==========================================================
# TRAINING DATA
# ==========================================================

DEFAULT_TRAINING_DATA = [
    ("engine", "My engine will not start"),
    ("engine", "The car engine stopped suddenly"),
    ("engine", "Vehicle has engine problems"),
    ("engine", "Engine is making strange noise"),

    ("brake", "My brakes are not working"),
    ("brake", "The brake pedal feels weak"),
    ("brake", "I have a braking problem"),
    ("brake", "The car cannot stop properly"),

    ("tyre", "I have a flat tyre"),
    ("tyre", "My tire has a puncture"),
    ("tyre", "The wheel is damaged"),
    ("tyre", "There is a tyre problem"),

    ("battery", "My battery is dead"),
    ("battery", "The car battery is not working"),
    ("battery", "I need a jump start"),
    ("battery", "Vehicle battery has no power"),

    ("electrical", "There is an electrical problem"),
    ("electrical", "The vehicle wiring is damaged"),
    ("electrical", "The lights are not working"),
    ("electrical", "There is a fuse problem"),

    ("fuel", "The car has no fuel"),
    ("fuel", "I ran out of petrol"),
    ("fuel", "The vehicle ran out of diesel"),
    ("fuel", "The fuel tank is empty"),

    ("overheating", "My engine is overheating"),
    ("overheating", "The vehicle temperature is too high"),
    ("overheating", "The engine is very hot"),
    ("overheating", "There is a coolant problem"),

    ("accident", "I was involved in an accident"),
    ("accident", "The vehicle had a collision"),
    ("accident", "My car crashed"),
    ("accident", "There has been an accident"),
]


# ==========================================================
# TEXT PROCESSING
# ==========================================================

def normalize_text(text: str) -> str:
    """
    Normalize text for training and prediction.
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


def tokenize(text: str):
    """
    Convert text into normalized tokens.
    """

    normalized = normalize_text(text)

    if not normalized:
        return []

    return normalized.split()


# ==========================================================
# TRAIN MODEL
# ==========================================================

def train_model(training_data=None):
    """
    Train a lightweight word-frequency classifier.

    Returns:
        {
            "success": True,
            "model": {...},
            "message": "..."
        }
    """

    if training_data is None:
        training_data = DEFAULT_TRAINING_DATA

    if not isinstance(training_data, list):
        return {
            "success": False,
            "message": "Training data must be a list.",
        }

    if not training_data:
        return {
            "success": False,
            "message": "Training data cannot be empty.",
        }

    class_word_counts = {}
    class_counts = Counter()

    for item in training_data:

        if not isinstance(item, (tuple, list)):
            continue

        if len(item) != 2:
            continue

        category, text = item

        if not isinstance(category, str):
            continue

        if not isinstance(text, str):
            continue

        category = category.strip().upper()

        tokens = tokenize(text)

        if not category or not tokens:
            continue

        if category not in class_word_counts:
            class_word_counts[category] = Counter()

        class_counts[category] += 1

        for token in tokens:
            class_word_counts[category][token] += 1

    if not class_word_counts:
        return {
            "success": False,
            "message": "No valid training records found.",
        }

    model = {
        "model_type": "word_frequency_classifier",
        "version": "1.0.0",
        "classes": sorted(class_word_counts.keys()),
        "class_counts": dict(class_counts),
        "word_counts": {
            category: dict(counter)
            for category, counter
            in class_word_counts.items()
        },
        "training_samples": sum(
            class_counts.values()
        ),
    }

    return {
        "success": True,
        "message": "Model trained successfully.",
        "model": model,
    }


# ==========================================================
# SAVE MODEL
# ==========================================================

def save_model(model, path=MODEL_FILE):
    """
    Save the trained model as JSON.
    """

    if not isinstance(model, dict):
        return {
            "success": False,
            "message": "Model must be a dictionary.",
        }

    try:
        path = Path(path)

        path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        with path.open(
            "w",
            encoding="utf-8",
        ) as file:

            json.dump(
                model,
                file,
                indent=4,
            )

        return {
            "success": True,
            "message": "Model saved successfully.",
            "path": str(path),
        }

    except OSError as error:

        return {
            "success": False,
            "message": f"Unable to save model: {error}",
        }


# ==========================================================
# LOAD MODEL
# ==========================================================

def load_model(path=MODEL_FILE):
    """
    Load a previously saved model.
    """

    path = Path(path)

    if not path.exists():
        return {
            "success": False,
            "message": "Model file not found.",
            "model": None,
        }

    try:
        with path.open(
            "r",
            encoding="utf-8",
        ) as file:

            model = json.load(file)

        return {
            "success": True,
            "message": "Model loaded successfully.",
            "model": model,
        }

    except (
        OSError,
        json.JSONDecodeError,
    ) as error:

        return {
            "success": False,
            "message": f"Unable to load model: {error}",
            "model": None,
        }


# ==========================================================
# TRAIN AND SAVE
# ==========================================================

def train_and_save(training_data=None):
    """
    Train the model and save it to disk.
    """

    training = train_model(training_data)

    if not training["success"]:
        return training

    saving = save_model(
        training["model"]
    )

    if not saving["success"]:
        return saving

    return {
        "success": True,
        "message": "Model trained and saved successfully.",
        "model": training["model"],
        "path": saving["path"],
    }


# ==========================================================
# TEST
# ==========================================================

if __name__ == "__main__":

    print("=" * 60)
    print("RSA ML MODEL TRAINING TEST")
    print("=" * 60)

    # ------------------------------------------------------
    # Training
    # ------------------------------------------------------

    training = train_model()

    print(
        "Model training      :",
        "PASS"
        if training["success"]
        else "FAIL"
    )

    if training["success"]:

        model = training["model"]

        print(
            "Training samples    :",
            model["training_samples"]
        )

        print(
            "Classes discovered  :",
            len(model["classes"])
        )

        # --------------------------------------------------
        # Required classes
        # --------------------------------------------------

        required_classes = {
            "ENGINE",
            "BRAKE",
            "TYRE",
            "BATTERY",
            "ELECTRICAL",
            "FUEL",
            "OVERHEATING",
            "ACCIDENT",
        }

        print(
            "Class validation    :",
            "PASS"
            if required_classes.issubset(
                set(model["classes"])
            )
            else "FAIL"
        )

        # --------------------------------------------------
        # Save
        # --------------------------------------------------

        saving = save_model(model)

        print(
            "Model saving        :",
            "PASS"
            if saving["success"]
            else "FAIL"
        )

        # --------------------------------------------------
        # Load
        # --------------------------------------------------

        loading = load_model()

        print(
            "Model loading       :",
            "PASS"
            if loading["success"]
            else "FAIL"
        )

        # --------------------------------------------------
        # Integrity
        # --------------------------------------------------

        integrity_pass = (
            loading["success"]
            and loading["model"]["classes"]
            == model["classes"]
            and loading["model"]["training_samples"]
            == model["training_samples"]
        )

        print(
            "Model integrity     :",
            "PASS"
            if integrity_pass
            else "FAIL"
        )

    print("=" * 60)
    print("RSA ML MODEL TRAINING TEST COMPLETE")
    print("=" * 60)