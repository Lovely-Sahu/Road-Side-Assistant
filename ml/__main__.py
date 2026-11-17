"""
RSA Machine Learning Package Entry Point
"""

from . import get_ml_info


def main():
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
        "PASS" if info["status"] == "active" else "FAIL"
    )

    print("=" * 60)
    print("RSA MACHINE LEARNING PACKAGE TEST COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    main()