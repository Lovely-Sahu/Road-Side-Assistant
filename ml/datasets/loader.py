"""
RSA ML Dataset Loader
---------------------

Provides safe utilities for loading and validating
CSV datasets used by the RSA machine-learning system.
"""

from pathlib import Path
import csv


# ----------------------------------------------------------
# DATASET DIRECTORY
# ----------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent

SUPPORTED_EXTENSIONS = {".csv"}


# ----------------------------------------------------------
# FIND DATASET
# ----------------------------------------------------------

def find_dataset(filename: str):
    """
    Return the path of a dataset inside the datasets folder.
    """

    if not isinstance(filename, str) or not filename.strip():
        return None

    path = BASE_DIR / filename

    if path.exists() and path.is_file():
        return path

    return None


# ----------------------------------------------------------
# LOAD CSV DATASET
# ----------------------------------------------------------

def load_csv(filename: str):
    """
    Load a CSV dataset and return it as a list of dictionaries.
    """

    path = find_dataset(filename)

    if path is None:
        return {
            "success": False,
            "message": "Dataset file not found.",
            "data": [],
        }

    if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
        return {
            "success": False,
            "message": "Unsupported dataset format.",
            "data": [],
        }

    try:
        with path.open(
            "r",
            encoding="utf-8",
            newline=""
        ) as file:

            reader = csv.DictReader(file)

            data = list(reader)

        return {
            "success": True,
            "message": "Dataset loaded successfully.",
            "data": data,
            "rows": len(data),
            "columns": reader.fieldnames or [],
        }

    except (OSError, csv.Error) as error:

        return {
            "success": False,
            "message": f"Unable to load dataset: {error}",
            "data": [],
        }


# ----------------------------------------------------------
# VALIDATE DATASET
# ----------------------------------------------------------

def validate_dataset(data):
    """
    Validate that the loaded dataset has usable records.
    """

    if not isinstance(data, list):
        return {
            "success": False,
            "message": "Dataset must be a list.",
        }

    if not data:
        return {
            "success": False,
            "message": "Dataset is empty.",
        }

    if not all(isinstance(row, dict) for row in data):
        return {
            "success": False,
            "message": "Dataset contains invalid records.",
        }

    return {
        "success": True,
        "message": "Dataset is valid.",
        "rows": len(data),
    }


# ----------------------------------------------------------
# DATASET SUMMARY
# ----------------------------------------------------------

def get_dataset_summary(data):
    """
    Return basic information about a dataset.
    """

    validation = validate_dataset(data)

    if not validation["success"]:
        return validation

    columns = list(data[0].keys()) if data else []

    return {
        "success": True,
        "rows": len(data),
        "columns": columns,
        "column_count": len(columns),
    }


# ----------------------------------------------------------
# TEST
# ----------------------------------------------------------

if __name__ == "__main__":

    print("=" * 60)
    print("RSA ML DATASET LOADER TEST")
    print("=" * 60)

    # Test dataset validation
    sample_data = [
        {
            "incident_type": "battery",
            "severity": "medium",
        },
        {
            "incident_type": "tyre",
            "severity": "high",
        },
    ]

    validation = validate_dataset(sample_data)

    print(
        "Dataset validation :",
        "PASS" if validation["success"] else "FAIL"
    )

    # Test summary
    summary = get_dataset_summary(sample_data)

    print(
        "Dataset summary    :",
        "PASS" if summary["success"] else "FAIL"
    )

    print(
        "Rows               :",
        summary.get("rows", 0)
    )

    print(
        "Columns            :",
        summary.get("column_count", 0)
    )

    # Test missing dataset
    missing = load_csv("__rsa_missing_dataset__.csv")

    print(
        "Missing dataset    :",
        "PASS" if not missing["success"] else "FAIL"
    )

    print("=" * 60)
    print("RSA ML DATASET LOADER TEST COMPLETE")
    print("=" * 60)