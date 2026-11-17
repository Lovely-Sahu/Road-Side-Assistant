"""
RSA Machine Learning Package
----------------------------

Central package for the Roadside Assistance
machine-learning system.
"""

PACKAGE_NAME = "RSA Machine Learning"
PACKAGE_VERSION = "1.0.0"


# ==========================================================
# PACKAGE INFORMATION
# ==========================================================

def get_ml_info():
    """
    Return information about the RSA ML package.
    """

    return {
        "package": PACKAGE_NAME,
        "version": PACKAGE_VERSION,
        "status": "active",
        "components": [
            "datasets",
            "models",
            "training",
            "evaluation",
        ],
    }


# ==========================================================
# PACKAGE EXPORTS
# ==========================================================

__all__ = [
    "PACKAGE_NAME",
    "PACKAGE_VERSION",
    "get_ml_info",
]


# ==========================================================
# TEST
# ==========================================================

if __name__ == "__main__":

    print("=" * 60)
    print("RSA MACHINE LEARNING PACKAGE TEST")
    print("=" * 60)

    info = get_ml_info()

    print("Package :", info["package"])
    print("Version :", info["version"])
    print("Status  :", info["status"])

    print()
    print("Components:")

    for component in info["components"]:
        print("  -", component)

    print()

    print(
        "Package status :",
        "PASS"
        if info["status"] == "active"
        else "FAIL"
    )

    print("=" * 60)
    print("RSA MACHINE LEARNING PACKAGE TEST COMPLETE")
    print("=" * 60)