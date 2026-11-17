"""
RSA Machine Learning Models
---------------------------

Core model definitions and model metadata for the
Roadside Assistance machine-learning system.
"""

PACKAGE_NAME = "RSA ML Models"
PACKAGE_VERSION = "1.0.0"


def get_model_package_info():
    """
    Return information about the RSA ML model package.
    """

    return {
        "package": PACKAGE_NAME,
        "version": PACKAGE_VERSION,
        "status": "active",
    }


if __name__ == "__main__":

    print("=" * 60)
    print("RSA ML MODELS PACKAGE TEST")
    print("=" * 60)

    info = get_model_package_info()

    print("Package :", info["package"])
    print("Version :", info["version"])
    print(
        "Status  :",
        "PASS" if info["status"] == "active" else "FAIL"
    )

    print("=" * 60)
    print("RSA ML MODELS PACKAGE TEST COMPLETE")
    print("=" * 60)