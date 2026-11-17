"""
RSA Driver Package
------------------
Driver-side modules for the Roadside Assistance application.
"""

# ------------------------------------------------------------------
# PACKAGE INFORMATION
# ------------------------------------------------------------------

__version__ = "1.0.0"

__author__ = "RSA Development Team"

PACKAGE_NAME = "RSA Driver"


# ------------------------------------------------------------------
# DRIVER MODULE INFORMATION
# ------------------------------------------------------------------

def get_driver_module_info():
    """
    Return information about the Driver package.
    """

    return {
        "package": PACKAGE_NAME,
        "version": __version__,
        "author": __author__,
        "modules": [
            "dashboard",
            "emergency",
            "history",
            "report_problem",
            "vehicle",
        ],
        "status": "active",
    }


# ------------------------------------------------------------------
# PACKAGE EXPORTS
# ------------------------------------------------------------------

__all__ = [
    "get_driver_module_info",
    "PACKAGE_NAME",
    "__version__",
    "__author__",
]


# ------------------------------------------------------------------
# TEST
# ------------------------------------------------------------------

if __name__ == "__main__":

    print("=" * 60)
    print("RSA DRIVER PACKAGE TEST")
    print("=" * 60)

    info = get_driver_module_info()

    print("Package       :", info["package"])
    print("Version       :", info["version"])
    print("Author        :", info["author"])
    print("Status        :", info["status"])
    print("Modules       :", len(info["modules"]))

    print()

    print("Module list:")

    for module in info["modules"]:
        print("  -", module)

    print()

    print(
        "Package import :",
        "PASS"
        if info["status"] == "active"
        else "FAIL"
    )

    print("=" * 60)
    print("RSA DRIVER PACKAGE TEST COMPLETE")
    print("=" * 60)