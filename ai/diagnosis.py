# ============================================================
# RSA AI - DIAGNOSIS ENGINE
# ============================================================

class DiagnosisEngine:

    def __init__(self):

        # ----------------------------------------------------
        # DIAGNOSIS DATABASE
        # ----------------------------------------------------

        self.diagnosis_data = {

            "engine_overheating": {
                "title": "Engine Overheating",
                "possible_causes": [
                    "Low coolant level",
                    "Coolant leak",
                    "Radiator problem",
                    "Cooling fan failure",
                    "Thermostat failure",
                    "Engine overheating due to excessive heat"
                ],
                "diagnosis": (
                    "The vehicle is showing symptoms consistent with "
                    "engine overheating. The cooling system should be "
                    "checked before the vehicle is driven again."
                )
            },

            "brake_failure": {
                "title": "Brake Failure",
                "possible_causes": [
                    "Low brake fluid",
                    "Brake fluid leak",
                    "Brake pad or brake component failure",
                    "Brake hydraulic system problem",
                    "Brake master cylinder problem"
                ],
                "diagnosis": (
                    "The vehicle is showing symptoms consistent with "
                    "a braking system failure. The braking system "
                    "requires immediate professional inspection."
                )
            },

            "tyre_puncture": {
                "title": "Tyre Puncture",
                "possible_causes": [
                    "Punctured tyre",
                    "Sharp object in tyre",
                    "Tyre damage",
                    "Tyre valve problem",
                    "Tyre sidewall damage"
                ],
                "diagnosis": (
                    "The vehicle appears to have a punctured or damaged "
                    "tyre. The tyre should be inspected and repaired or "
                    "replaced before normal driving."
                )
            },

            "battery_failure": {
                "title": "Battery Failure",
                "possible_causes": [
                    "Discharged battery",
                    "Weak or old battery",
                    "Battery terminal problem",
                    "Alternator charging problem",
                    "Electrical system drain"
                ],
                "diagnosis": (
                    "The symptoms are consistent with a battery or "
                    "vehicle starting-system problem. The battery and "
                    "charging system should be inspected."
                )
            },

            "engine_failure": {
                "title": "Engine Failure",
                "possible_causes": [
                    "Engine mechanical failure",
                    "Fuel delivery problem",
                    "Electrical or ignition problem",
                    "Sensor failure",
                    "Engine overheating",
                    "Engine control system problem"
                ],
                "diagnosis": (
                    "The vehicle appears to have experienced an engine "
                    "failure or unexpected engine shutdown. Professional "
                    "diagnosis is required before continuing to drive."
                )
            },

            "accident": {
                "title": "Vehicle Accident",
                "possible_causes": [
                    "Collision",
                    "Impact damage",
                    "Body damage",
                    "Mechanical damage caused by impact",
                    "Electrical damage caused by collision"
                ],
                "diagnosis": (
                    "The vehicle has been involved in an accident or "
                    "collision. The vehicle should be inspected for "
                    "visible and hidden mechanical or structural damage."
                )
            },

            "fuel_problem": {
                "title": "Fuel Problem",
                "possible_causes": [
                    "Vehicle ran out of fuel",
                    "Incorrect fuel level",
                    "Fuel delivery problem",
                    "Fuel pump problem",
                    "Fuel system blockage"
                ],
                "diagnosis": (
                    "The symptoms are consistent with a fuel-related "
                    "problem. The fuel level and fuel delivery system "
                    "should be checked."
                )
            },

            "electrical_failure": {
                "title": "Electrical Failure",
                "possible_causes": [
                    "Electrical system failure",
                    "Blown fuse",
                    "Wiring problem",
                    "Battery or alternator problem",
                    "Electrical control module failure"
                ],
                "diagnosis": (
                    "The vehicle is showing symptoms consistent with "
                    "an electrical system problem. The electrical system "
                    "should be professionally inspected."
                )
            },

            "unknown": {
                "title": "Unknown Vehicle Problem",
                "possible_causes": [
                    "Mechanical problem",
                    "Electrical problem",
                    "Sensor issue",
                    "Warning system issue",
                    "Cause cannot be determined from the description"
                ],
                "diagnosis": (
                    "No specific vehicle problem could be identified "
                    "from the provided description. A professional "
                    "vehicle inspection is recommended."
                )
            }
        }

    # --------------------------------------------------------
    # GET DIAGNOSIS
    # --------------------------------------------------------

    def get_diagnosis(self, problem):

        if not problem:
            problem = "unknown"

        data = self.diagnosis_data.get(
            problem,
            self.diagnosis_data["unknown"]
        )

        return {
            "problem": problem,
            "title": data["title"],
            "diagnosis": data["diagnosis"],
            "possible_causes": data["possible_causes"]
        }

    # --------------------------------------------------------
    # GENERATE DIAGNOSIS
    # --------------------------------------------------------

    def diagnose(self, problem, description=None, analysis=None):
        """
        Build a diagnosis for a detected (predicted) problem.

        The original keys (problem, title, diagnosis, possible_causes) are
        unchanged. Additive keys make the result explicit about what it is:
        a model prediction from a text description, never a confirmed
        mechanical diagnosis, plus conservative safety guidance.

        ``analysis`` is the IncidentAnalyzer result (optional); when given,
        its hazards, severity and smoke/smell context shape the guidance.
        """

        result = self.get_diagnosis(problem)

        analysis = analysis or {}
        hazards = {h.get("hazard") for h in analysis.get("hazards", []) if isinstance(h, dict)}
        severity = str(analysis.get("severity") or "").upper()
        safe_to_drive = analysis.get("safe_to_drive")

        causes = list(result["possible_causes"])

        # Smoke from an engine has several possible causes; never pretend it is
        # only overheating.
        if problem == "engine_overheating" and "smoke" in hazards:
            causes.extend([
                "Oil leaking onto hot engine parts",
                "Electrical wiring fault (burning insulation)",
            ])

        safety_steps = list(SAFETY_STEPS.get(problem, SAFETY_STEPS["unknown"]))

        # Hazard guidance is prepended: life safety before vehicle advice.
        hazard_steps = []
        for hazard in ("injury", "fire", "fuel_leak", "smoke", "brake_loss", "burning_smell", "steam"):
            if hazard in hazards:
                hazard_steps.extend(HAZARD_STEPS[hazard])
        if problem == "accident" and "injury" not in hazards:
            hazard_steps.extend(HAZARD_STEPS["accident_check"])
        safety_steps = _dedupe(hazard_steps + safety_steps)

        emergency_services_advised = bool(hazards & {"injury", "fire", "fuel_leak"}) or problem == "accident"

        recommend_towing = (
            problem in {"brake_failure", "accident", "engine_failure"}
            or bool(hazards & {"fire", "smoke", "fuel_leak", "brake_loss"})
            or (problem == "engine_overheating" and severity == "CRITICAL")
            or safe_to_drive is False and severity == "CRITICAL"
        )

        return {
            "problem": result["problem"],
            "title": result["title"],
            "diagnosis": result["diagnosis"],
            "possible_causes": result["possible_causes"],

            # ----- additive structured fields -----
            "likely_causes": _dedupe(causes),
            "is_confirmed": False,
            "diagnosis_type": "ai_prediction_from_description",
            "disclaimer": (
                "This is an automated prediction based only on the description you "
                "entered. It is not a confirmed mechanical diagnosis; a qualified "
                "technician must inspect the vehicle."
            ),
            "safety_steps": safety_steps,
            "recommend_towing": recommend_towing,
            "recommend_professional_inspection": True,
            "emergency_services_advised": emergency_services_advised,
            "emergency_number_note": (
                "In India dial 112 for police, fire and ambulance. RSA providers are "
                "not an emergency medical or fire service."
            ) if emergency_services_advised else None,
        }


# ============================================================
# SAFETY GUIDANCE (conservative, non-diagnostic)
# ============================================================

def _dedupe(items):
    seen = set()
    output = []
    for item in items:
        if item not in seen:
            seen.add(item)
            output.append(item)
    return output


HAZARD_STEPS = {
    "injury": [
        "If anyone is injured, call 112 for an ambulance first. Do not move a seriously injured person unless they are in immediate danger.",
    ],
    "fire": [
        "If you see flames: switch off the ignition, get everyone out, move at least 30 metres away and call 112. Do not open the bonnet.",
    ],
    "fuel_leak": [
        "Fuel smell or leak: switch off the engine, do not start it again, no smoking or naked flames, move everyone away from the vehicle.",
    ],
    "smoke": [
        "Smoke: pull over safely, switch off the engine and get everyone out of the vehicle. Do not open the bonnet while smoke is coming out. If smoke increases or you see flames, move away and call 112.",
    ],
    "brake_loss": [
        "Brakes not working: do not drive the vehicle again. Use hazard lights; the vehicle must be towed.",
    ],
    "burning_smell": [
        "Burning smell: stop safely, switch off the engine and wait outside the vehicle until it is inspected.",
    ],
    "steam": [
        "Steam: switch off the engine and do not open the radiator or coolant cap while hot — it can cause severe burns.",
    ],
    "accident_check": [
        "Check everyone for injuries; call 112 if anyone is hurt or the road is blocked.",
    ],
}

SAFETY_STEPS = {
    "engine_overheating": [
        "Stop driving: continuing with an overheating engine can cause severe damage.",
        "Let the engine cool for at least 30 minutes before any inspection.",
    ],
    "brake_failure": [
        "Do not attempt to drive further. Arrange towing.",
        "Turn on hazard lights and stay away from traffic.",
    ],
    "tyre_puncture": [
        "Do not drive on a flat or burst tyre.",
        "Only change the tyre yourself if you are well away from traffic on firm, level ground.",
    ],
    "battery_failure": [
        "Turn off lights and accessories.",
        "Only jump-start if you know the correct procedure; otherwise wait for assistance.",
    ],
    "engine_failure": [
        "Switch on hazard lights and move people to a safe place away from traffic.",
        "Do not repeatedly try to restart the engine.",
    ],
    "accident": [
        "Switch on hazard lights and place a warning triangle if it is safe to do so.",
        "Do not drive the vehicle until it has been inspected.",
    ],
    "fuel_problem": [
        "Park safely off the road with hazard lights on.",
    ],
    "electrical_failure": [
        "If headlights or indicators failed, do not drive in the dark — wait in a safe place.",
    ],
    "unknown": [
        "The problem could not be identified. Treat the vehicle as unsafe until inspected.",
        "Wait in a safe place away from traffic.",
    ],
}


# ============================================================
# TEST
# ============================================================

if __name__ == "__main__":

    diagnosis_engine = DiagnosisEngine()

    test_cases = [

        (
            "ENGINE OVERHEATING",
            "engine_overheating"
        ),

        (
            "BRAKE FAILURE",
            "brake_failure"
        ),

        (
            "TYRE PUNCTURE",
            "tyre_puncture"
        ),

        (
            "BATTERY FAILURE",
            "battery_failure"
        ),

        (
            "ENGINE FAILURE",
            "engine_failure"
        ),

        (
            "ACCIDENT",
            "accident"
        ),

        (
            "FUEL PROBLEM",
            "fuel_problem"
        ),

        (
            "ELECTRICAL FAILURE",
            "electrical_failure"
        ),

        (
            "UNKNOWN",
            "unknown"
        )
    ]

    print()
    print("=" * 75)
    print("RSA AI DIAGNOSIS ENGINE - TEST SUITE")
    print("=" * 75)

    total_tests = 0
    passed_tests = 0
    failed_tests = 0

    for test_name, problem in test_cases:

        total_tests += 1

        print()
        print("-" * 75)
        print(f"TEST              : {test_name}")
        print(f"Problem           : {problem}")
        print("-" * 75)

        try:

            result = diagnosis_engine.diagnose(problem)

            if (
                result["problem"] == problem
                and result["title"]
                and result["diagnosis"]
                and result["possible_causes"]
            ):

                passed_tests += 1

                print("STATUS            : PASS")
                print(f"Title             : {result['title']}")
                print(f"Diagnosis         : {result['diagnosis']}")
                print("Possible Causes   :")

                for cause in result["possible_causes"]:
                    print(f"  - {cause}")

            else:

                failed_tests += 1

                print("STATUS            : FAIL")

        except Exception as e:

            failed_tests += 1

            print("STATUS            : FAIL")
            print(f"Error             : {e}")

    print()
    print("=" * 75)
    print("RSA AI DIAGNOSIS TEST RESULTS")
    print("=" * 75)

    print(f"TOTAL TESTS       : {total_tests}")
    print(f"PASSED            : {passed_tests}")
    print(f"FAILED            : {failed_tests}")

    print("=" * 75)

    if failed_tests == 0:

        print("ALL TESTS PASSED")
        print("RSA DIAGNOSIS ENGINE IS WORKING CORRECTLY")

    else:

        print("SOME TESTS FAILED")

    print("=" * 75)