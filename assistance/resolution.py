"""
RSA - Assistance Resolution Engine

Responsible for resolving roadside assistance requests,
selecting the appropriate service, priority, and escalation
requirements.
"""

from datetime import datetime
from typing import Any, Dict, Optional


class ResolutionEngine:

    SERVICE_DETAILS = {
        "emergency_services": {
            "category": "Emergency",
            "description": "Emergency response for accidents and critical incidents.",
            "default_priority": "EMERGENCY",
        },

        "emergency_roadside_assistance": {
            "category": "Emergency Roadside Assistance",
            "description": "Immediate roadside assistance for dangerous vehicle failures.",
            "default_priority": "EMERGENCY",
        },

        "mechanic_or_roadside_assistance": {
            "category": "Mechanical Assistance",
            "description": "Mechanic or roadside assistance for vehicle mechanical failures.",
            "default_priority": "URGENT",
        },

        "tyre_assistance": {
            "category": "Tyre Assistance",
            "description": "Professional tyre repair or replacement assistance.",
            "default_priority": "URGENT",
        },

        "battery_assistance": {
            "category": "Battery Assistance",
            "description": "Battery jump-start, testing, or replacement assistance.",
            "default_priority": "NORMAL",
        },

        "fuel_delivery": {
            "category": "Fuel Delivery",
            "description": "Fuel delivery service for vehicles that have run out of fuel.",
            "default_priority": "NORMAL",
        },

        "electrical_vehicle_assistance": {
            "category": "Electrical Vehicle Assistance",
            "description": "Vehicle electrical system inspection and roadside assistance.",
            "default_priority": "NORMAL",
        },

        "general_roadside_assistance": {
            "category": "General Roadside Assistance",
            "description": "General roadside diagnosis and assistance.",
            "default_priority": "LOW",
        },
    }

    def __init__(self):
        self.resolution_history = []

    # ------------------------------------------------------------------
    # MAIN RESOLUTION METHOD
    # ------------------------------------------------------------------

    def resolve(
        self,
        problem: str,
        assistance_type: str,
        priority: Optional[str] = None,
        safe_to_drive: bool = True,
        escalation: bool = False,
    ) -> Dict[str, Any]:

        problem = str(problem or "unknown").strip().lower()

        assistance_type = str(
            assistance_type or "general_roadside_assistance"
        ).strip().lower()

        # Get service information
        service = self.SERVICE_DETAILS.get(
            assistance_type,
            self.SERVICE_DETAILS["general_roadside_assistance"],
        )

        # --------------------------------------------------------------
        # PRIORITY
        # --------------------------------------------------------------
        #
        # IMPORTANT:
        # escalation does NOT automatically mean EMERGENCY.
        #
        # Example:
        # engine_failure -> URGENT + escalation=True
        # tyre_puncture  -> URGENT + escalation=True
        # brake_failure  -> EMERGENCY + escalation=True
        #
        # The priority supplied by the decision engine is respected.
        # --------------------------------------------------------------

        if priority:
            final_priority = str(priority).strip().upper()
        else:
            final_priority = service["default_priority"]

        # --------------------------------------------------------------
        # DRIVE STATUS
        # --------------------------------------------------------------

        if safe_to_drive:
            drive_status = "DRIVE ONLY IF SAFE"
        else:
            drive_status = "DO NOT DRIVE"

        # --------------------------------------------------------------
        # BUILD RESOLUTION
        # --------------------------------------------------------------

        resolution = {
            "resolved": True,

            "problem": problem,

            "assistance_type": assistance_type,

            "service_category": service["category"],

            "service_description": service["description"],

            "priority": final_priority,

            "safe_to_drive": bool(safe_to_drive),

            "drive_status": drive_status,

            "escalation_required": bool(escalation),

            "status": "REQUEST_READY",

            "message": self._build_message(
                problem=problem,
                assistance_type=assistance_type,
                priority=final_priority,
                safe_to_drive=safe_to_drive,
                escalation=escalation,
            ),

            "created_at": datetime.now().isoformat(
                timespec="seconds"
            ),
        }

        self.resolution_history.append(resolution)

        return resolution

    # ------------------------------------------------------------------
    # MESSAGE GENERATOR
    # ------------------------------------------------------------------

    def _build_message(
        self,
        problem: str,
        assistance_type: str,
        priority: str,
        safe_to_drive: bool,
        escalation: bool,
    ) -> str:

        service = self.SERVICE_DETAILS.get(
            assistance_type,
            self.SERVICE_DETAILS["general_roadside_assistance"],
        )

        service_name = service["category"]

        # EMERGENCY
        if priority == "EMERGENCY":
            return (
                f"Emergency assistance is required for {problem}. "
                f"Recommended service: {service_name}. "
                f"Do not continue driving and contact assistance immediately."
            )

        # URGENT
        if priority == "URGENT":
            return (
                f"Urgent roadside assistance is recommended for {problem}. "
                f"Recommended service: {service_name}."
            )

        # NORMAL
        if priority == "NORMAL":
            return (
                f"Roadside assistance is recommended for {problem}. "
                f"Recommended service: {service_name}."
            )

        # LOW
        return (
            f"The incident appears to be low risk. "
            f"Recommended service: {service_name}."
        )

    # ------------------------------------------------------------------
    # SERVICE DETAILS
    # ------------------------------------------------------------------

    def get_service_details(
        self,
        assistance_type: str,
    ) -> Dict[str, Any]:

        assistance_type = str(
            assistance_type or "general_roadside_assistance"
        ).strip().lower()

        return self.SERVICE_DETAILS.get(
            assistance_type,
            self.SERVICE_DETAILS["general_roadside_assistance"],
        ).copy()

    # ------------------------------------------------------------------
    # HISTORY
    # ------------------------------------------------------------------

    def get_history(self):
        return list(self.resolution_history)

    def clear_history(self):
        self.resolution_history.clear()


# ----------------------------------------------------------------------
# CONVENIENCE FUNCTION
# ----------------------------------------------------------------------

def resolve_assistance(
    problem: str,
    assistance_type: str,
    priority: Optional[str] = None,
    safe_to_drive: bool = True,
    escalation: bool = False,
) -> Dict[str, Any]:

    engine = ResolutionEngine()

    return engine.resolve(
        problem=problem,
        assistance_type=assistance_type,
        priority=priority,
        safe_to_drive=safe_to_drive,
        escalation=escalation,
    )


# ======================================================================
# TEST SUITE
# ======================================================================

def run_tests():

    print("=" * 75)
    print("RSA ASSISTANCE RESOLUTION ENGINE - TEST SUITE")
    print("=" * 75)

    engine = ResolutionEngine()

    test_cases = [

        {
            "name": "BRAKE FAILURE",
            "problem": "brake_failure",
            "service": "emergency_roadside_assistance",
            "priority": "EMERGENCY",
            "safe": False,
            "escalation": True,
        },

        {
            "name": "ACCIDENT",
            "problem": "accident",
            "service": "emergency_services",
            "priority": "EMERGENCY",
            "safe": False,
            "escalation": True,
        },

        {
            "name": "ENGINE OVERHEATING",
            "problem": "engine_overheating",
            "service": "mechanic_or_roadside_assistance",
            "priority": "EMERGENCY",
            "safe": False,
            "escalation": True,
        },

        {
            "name": "ENGINE FAILURE",
            "problem": "engine_failure",
            "service": "mechanic_or_roadside_assistance",
            "priority": "URGENT",
            "safe": False,
            "escalation": True,
        },

        {
            "name": "TYRE PUNCTURE",
            "problem": "tyre_puncture",
            "service": "tyre_assistance",
            "priority": "URGENT",
            "safe": False,
            "escalation": True,
        },

        {
            "name": "BATTERY FAILURE",
            "problem": "battery_failure",
            "service": "battery_assistance",
            "priority": "NORMAL",
            "safe": True,
            "escalation": False,
        },

        {
            "name": "FUEL PROBLEM",
            "problem": "fuel_problem",
            "service": "fuel_delivery",
            "priority": "NORMAL",
            "safe": True,
            "escalation": False,
        },

        {
            "name": "ELECTRICAL FAILURE",
            "problem": "electrical_failure",
            "service": "electrical_vehicle_assistance",
            "priority": "NORMAL",
            "safe": True,
            "escalation": False,
        },

        {
            "name": "UNKNOWN",
            "problem": "unknown",
            "service": "general_roadside_assistance",
            "priority": "LOW",
            "safe": True,
            "escalation": False,
        },
    ]

    passed = 0
    failed = 0

    for test in test_cases:

        result = engine.resolve(
            problem=test["problem"],
            assistance_type=test["service"],
            priority=test["priority"],
            safe_to_drive=test["safe"],
            escalation=test["escalation"],
        )

        status = (
            result["problem"] == test["problem"]
            and result["assistance_type"] == test["service"]
            and result["priority"] == test["priority"]
            and result["safe_to_drive"] == test["safe"]
            and result["escalation_required"] == test["escalation"]
            and result["resolved"] is True
        )

        if status:
            passed += 1
            status_text = "PASS"
        else:
            failed += 1
            status_text = "FAIL"

        print("\n" + "-" * 75)

        print(f"TEST              : {test['name']}")
        print(f"STATUS            : {status_text}")

        print(f"Expected Service  : {test['service']}")
        print(f"Actual Service    : {result['assistance_type']}")

        print(f"Expected Priority : {test['priority']}")
        print(f"Actual Priority   : {result['priority']}")

        print(f"Escalation        : {result['escalation_required']}")

        print(f"Safe To Drive     : {result['safe_to_drive']}")

        print(f"Status            : {result['status']}")

        print(f"Message           : {result['message']}")

    # ------------------------------------------------------------------
    # FINAL RESULTS
    # ------------------------------------------------------------------

    print("\n" + "=" * 75)
    print("RSA ASSISTANCE RESOLUTION ENGINE TEST RESULTS")
    print("=" * 75)

    print(f"TOTAL TESTS       : {len(test_cases)}")
    print(f"PASSED            : {passed}")
    print(f"FAILED            : {failed}")

    print("=" * 75)

    if failed == 0:

        print("ALL TESTS PASSED")
        print(
            "RSA ASSISTANCE RESOLUTION ENGINE "
            "IS WORKING CORRECTLY"
        )

    else:

        print("SOME TESTS FAILED")

    print("=" * 75)


# ======================================================================
# MAIN
# ======================================================================

if __name__ == "__main__":
    run_tests()