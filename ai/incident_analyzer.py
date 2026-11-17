import re

# Machine-learning second opinion (TF-IDF + Logistic Regression / Random Forest).
# Optional: without scikit-learn the analyzer simply uses the rules.
try:
    from ml.incident_models import OTHER as ML_OTHER, get_incident_models, ml_enabled
except Exception:  # noqa: BLE001
    get_incident_models = None
    ML_OTHER = "other"

    def ml_enabled():
        return False


# =============================================================
# SUPPORTED INCIDENT TYPES
# =============================================================

SUPPORTED_PROBLEMS = (
    "engine_overheating",
    "brake_failure",
    "tyre_puncture",
    "battery_failure",
    "engine_failure",
    "accident",
    "fuel_problem",
    "electrical_failure",
)

PROBLEM_LABELS = {
    "engine_overheating": "Engine overheating",
    "brake_failure": "Brake failure",
    "tyre_puncture": "Tyre puncture / damage",
    "battery_failure": "Battery / starting problem",
    "engine_failure": "Engine stopped / breakdown",
    "accident": "Accident / collision",
    "fuel_problem": "Out of fuel",
    "electrical_failure": "Electrical failure",
    "unknown": "Not identified",
}

CONFIDENCE_BASIS = (
    "Rule-based match strength from the words in the description. "
    "It is not a calibrated probability and not a mechanical diagnosis."
)

ML_CONFIDENCE_BASIS = (
    "From TF-IDF + Logistic Regression (checked against a Random Forest), trained on example "
    "descriptions; a prediction, not a mechanical diagnosis."
)


# =============================================================
# SYMPTOM VOCABULARY (word-proximity layer)
# -------------------------------------------------------------
# The phrase patterns below require exact word order
# ("smoke coming from the engine"). Drivers write freely
# ("smoke is coming out of my engine"), which previously
# produced "unknown". These term groups are matched as
# separate words that must occur close together in the same
# clause, so word order and filler words no longer matter.
# =============================================================

_TERMS = {
    "ENGINE_PART": ["engine", "bonnet", "hood", "motor", "radiator", "coolant", "engine bay"],
    "SMOKE": ["smoke", "smoking", "smoky", "steam", "steaming", "vapour", "vapor"],
    "HOT": ["hot", "overheat", "overheating", "overheated", "heating up", "temperature", "temp gauge",
            "temperature gauge", "temperature light", "red zone"],
    "BRAKE": ["brake", "brakes", "braking", "brake pedal"],
    "BRAKE_BAD": ["failed", "fail", "failing", "failure", "gone", "useless", "spongy", "soft",
                  "sinking", "unresponsive", "not working", "stopped working", "don't work",
                  "do not work", "doesn't work", "no response", "goes to the floor", "went to the floor",
                  "not responding", "aren't working", "are not working", "isn't working"],
    "TYRE": ["tyre", "tyres", "tire", "tires", "wheel", "wheels"],
    "TYRE_BAD": ["flat", "puncture", "punctured", "burst", "blown", "deflated", "deflating",
                 "leaking air", "lost air", "losing air", "no air", "low air", "bulge", "torn",
                 "slashed", "went down", "gone down"],
    "BATTERY": ["battery"],
    "BATTERY_BAD": ["dead", "flat", "drained", "draining", "weak", "died", "discharged", "low",
                    "not charging", "swollen", "won't charge"],
    "NO_START": ["won't start", "will not start", "wouldn't start", "doesn't start", "does not start",
                 "not starting", "cannot start", "can't start", "fails to start", "won't crank",
                 "will not crank", "just clicks", "clicking sound", "not turning over", "won't turn over"],
    "VEHICLE": ["car", "vehicle", "engine", "bike", "scooter", "truck", "van", "jeep", "suv"],
    "STOPPED": ["stopped", "stalled", "died", "shut off", "shut down", "cut out", "cutting out",
                "switched off", "broke down", "broken down", "stopped working", "stops", "stalls"],
    "FUEL": ["fuel", "petrol", "diesel", "gas", "cng"],
    "FUEL_EMPTY": ["out of", "ran out", "run out", "running out", "empty", "finished", "dry", "no"],
    "LEAK": ["leak", "leaking", "leaked", "dripping", "smell", "smells", "smelling"],
    "ELECTRICAL": ["lights", "light", "headlights", "headlight", "dashboard", "dash", "wiring",
                   "wires", "fuse", "fuses", "electrical", "electronics", "indicators", "horn",
                   "power windows", "instrument cluster"],
    "ELECTRICAL_BAD": ["not working", "blank", "dead", "failed", "flickering", "flicker",
                       "stopped working", "went off", "sparking", "sparks", "shorted"],
    "COLLISION_VERB": ["hit", "rammed", "bumped", "struck", "crashed into", "ran into"],
    "COLLISION_OBJECT": ["car", "vehicle", "truck", "bus", "bike", "scooter", "lorry", "auto",
                         "tree", "wall", "pole", "divider", "barrier", "someone", "pedestrian",
                         "me", "us", "my car", "another"],
}

# (problem, group A, group B, max word distance, evidence weight, description)
_PROXIMITY_RULES = [
    ("engine_overheating", "SMOKE", "ENGINE_PART", 6, 1.0, "smoke/steam near the engine"),
    ("engine_overheating", "HOT", "ENGINE_PART", 6, 1.0, "engine running hot"),
    ("brake_failure", "BRAKE", "BRAKE_BAD", 5, 1.2, "brakes not responding"),
    ("tyre_puncture", "TYRE", "TYRE_BAD", 5, 1.0, "tyre flat or damaged"),
    ("battery_failure", "BATTERY", "BATTERY_BAD", 4, 1.0, "battery weak or dead"),
    ("battery_failure", "VEHICLE", "NO_START", 5, 0.7, "vehicle will not start"),
    ("engine_failure", "VEHICLE", "STOPPED", 4, 0.7, "vehicle stopped or stalled"),
    ("fuel_problem", "FUEL_EMPTY", "FUEL", 3, 1.0, "fuel tank empty"),
    ("electrical_failure", "ELECTRICAL", "ELECTRICAL_BAD", 4, 1.0, "electrical component not working"),
    ("accident", "COLLISION_VERB", "COLLISION_OBJECT", 4, 1.0, "collision with an object or vehicle"),
]

# Hazard words: a negation directly before them ("no smoke") cancels them.
_HAZARDS = {
    "fire": ["fire", "flames", "flame", "on fire", "caught fire", "burning", "explosion", "exploded"],
    "smoke": ["smoke", "smoking"],
    "steam": ["steam", "steaming"],
    "fuel_leak": ["fuel leak", "petrol leak", "diesel leak", "gas leak", "leaking fuel", "leaking petrol",
                  "smell of petrol", "smell of fuel", "petrol smell", "fuel smell", "smell petrol",
                  "smell fuel", "smells of petrol", "smells of fuel"],
    "injury": ["injured", "injury", "injuries", "bleeding", "hurt", "unconscious", "wounded",
               "ambulance", "not breathing"],
    "brake_loss": ["brakes failed", "brake failure", "no brakes", "cannot stop", "can't stop",
                   "won't stop", "will not stop"],
    "burning_smell": ["burning smell", "smell of burning", "smells burning", "burnt smell", "smell burning"],
}

_NEGATORS = {"no", "without", "zero", "never"}
_NEGATING_PHRASES = ("no sign of", "no signs of", "not any", "there is no", "there's no", "isn't any",
                     "is not any", "wasn't any")

FOLLOW_UP_QUESTIONS = {
    "general": [
        "Is the engine still running, or did it stop?",
        "Do you see smoke, steam or flames, or smell burning or fuel?",
        "Are any warning lights on the dashboard? Which ones?",
        "Can the vehicle move safely, or is a tyre, brake or steering problem stopping it?",
        "Is anyone injured?",
    ],
    "engine_overheating": ["Is the temperature gauge or warning light in the red?",
                           "Is the smoke white/steam-like, or dark and smelling of burning?"],
    "engine_failure": ["Did the engine stop on its own while driving, or will it not start now?",
                       "Was there a warning light, noise or smell just before it stopped?"],
    "battery_failure": ["When you turn the key, do you hear clicking, slow cranking, or nothing at all?",
                        "Do the dashboard lights come on?"],
    "brake_failure": ["Does the brake pedal feel soft or go to the floor?",
                      "Is a brake warning light on?"],
    "tyre_puncture": ["Which tyre is affected, and is it completely flat or losing air slowly?",
                      "Do you have a usable spare tyre?"],
    "electrical_failure": ["Which components stopped working (lights, dashboard, windows, everything)?",
                           "Did you notice sparks or a burning smell?"],
    "fuel_problem": ["Did the fuel gauge show empty before the vehicle stopped?",
                     "Do you smell fuel (which could mean a leak rather than an empty tank)?"],
    "accident": ["Is anyone injured?", "Is the vehicle blocking traffic or leaking fluids?"],
}


class IncidentAnalyzer:

    SUPPORTED_PROBLEMS = SUPPORTED_PROBLEMS
    PROBLEM_LABELS = PROBLEM_LABELS

    def __init__(self, use_ml=None, ml_models=None):

        # Machine-learning second opinion (see ml/incident_models.py).
        self.use_ml = ml_enabled() if use_ml is None else bool(use_ml)
        self._ml_models = ml_models

        # =========================================================
        # PROBLEM PATTERNS
        # =========================================================

        self.problem_patterns = {

            "engine_overheating": [
                "engine overheating",
                "engine is overheating",
                "engine very hot",
                "engine is very hot",
                "engine hot",
                "engine is hot",
                "overheating",
                "overheated engine",
                "engine overheated",

                "temperature high",
                "temperature is high",
                "temperature warning",
                "engine temperature",
                "high engine temperature",
                "temperature is too high",

                "coolant",
                "coolant leak",
                "coolant is leaking",
                "coolant leaking",
                "coolant level low",

                "radiator",
                "radiator leak",
                "radiator leaking",

                "steam from engine",
                "steam coming from engine",
                "steam from the engine",
                "steam coming from the engine",

                "smoke from engine",
                "smoke coming from engine",
                "smoke from the engine",
                "smoke coming from the engine"
            ],

            "brake_failure": [
                "brakes failed",
                "brakes have failed",
                "brakes completely failed",
                "brakes have completely failed",

                "brake failure",
                "brake failed",
                "brake has failed",

                "brakes not working",
                "brakes are not working",
                "brakes completely stopped working",

                "brake not working",
                "brake is not working",

                "cannot brake",
                "can't brake",
                "cannot stop",
                "can't stop",

                "car won't stop",
                "car will not stop",
                "car cannot stop",
                "car can't stop",

                "vehicle won't stop",
                "vehicle will not stop",
                "vehicle cannot stop",
                "vehicle can't stop",

                "braking problem",
                "brake problem",

                "brake pedal failed",
                "brake pedal has failed",
                "brake pedal is not working",
                "brake pedal not working",

                "brakes have stopped working",
                "brakes stopped working"
            ],

            "tyre_puncture": [
                "tyre puncture",
                "tire puncture",

                "flat tyre",
                "flat tire",

                "tyre is flat",
                "tire is flat",

                "punctured tyre",
                "punctured tire",

                "tyre burst",
                "tire burst",

                "blown tyre",
                "blown tire",

                "flat wheel",
                "damaged tyre",
                "damaged tire"
            ],

            "battery_failure": [
                "battery dead",
                "battery is dead",
                "dead battery",

                "battery failure",
                "battery failed",
                "battery problem",
                "battery issue",

                "car won't start",
                "car will not start",
                "car cannot start",
                "car can't start",

                "vehicle won't start",
                "vehicle will not start",
                "vehicle cannot start",
                "vehicle can't start",

                "engine won't start",
                "engine will not start",
                "engine cannot start",
                "engine can't start",

                "starter won't work",
                "starter will not work",
                "starter is not working",

                "battery warning",
                "battery warning light",

                "no power",
                "car has no power"
            ],

            "engine_failure": [
                "engine stopped",
                "engine has stopped",
                "engine failure",
                "engine failed",

                "engine stalled",
                "engine has stalled",

                "engine suddenly stopped",
                "engine suddenly stops",

                "engine stopped while driving",
                "engine stopped while i was driving",

                "engine died",
                "engine suddenly died",

                "car stopped suddenly",
                "car suddenly stopped",

                "vehicle stopped suddenly",
                "vehicle suddenly stopped",

                "car broke down",
                "vehicle broke down"
            ],

            "accident": [
                "accident",
                "road accident",
                "car accident",
                "vehicle accident",

                "crash",
                "crashed",
                "car crashed",
                "vehicle crashed",

                "collision",
                "collided",

                "hit another car",
                "hit another vehicle",

                "vehicle hit",
                "car was hit",
                "vehicle was hit",

                "i was involved in a collision",
                "involved in a collision",

                "someone hit my car",
                "someone hit my vehicle"
            ],

            "fuel_problem": [
                "out of fuel",
                "out of petrol",
                "out of gas",

                "fuel empty",
                "petrol empty",

                "no fuel",
                "no petrol",
                "no gas",

                "ran out of fuel",
                "run out of fuel",

                "ran out of petrol",
                "run out of petrol",

                "ran out of gas",
                "run out of gas",

                "car has run out of fuel",
                "car has run out of petrol",

                "fuel problem",
                "fuel issue",

                "petrol problem",
                "petrol issue"
            ],

            "electrical_failure": [
                "electrical failure",
                "electrical problem",
                "electrical issue",

                "wiring problem",
                "wiring issue",

                "lights not working",
                "light not working",

                "headlights not working",
                "headlight not working",

                "dashboard went blank",
                "dashboard is blank",
                "dashboard blank",

                "electronics stopped",
                "electronics failed",

                "electrical system stopped",
                "electrical system failed",

                "power system failed",
                "power system stopped"
            ]
        }

        # =========================================================
        # SEVERITY RULES
        # =========================================================

        self.severity_rules = {

            "critical": [
                "fire",
                "flames",
                "explosion",

                "smoke",
                "smoke from engine",
                "smoke coming from engine",

                "brakes failed",
                "brakes have failed",
                "brakes completely failed",
                "brake failure",

                "cannot stop",
                "can't stop",
                "car won't stop",
                "car will not stop",
                "vehicle won't stop",
                "vehicle will not stop",

                "accident",
                "crash",
                "collision",

                "fuel leak",
                "petrol leak",
                "gas leak",

                "danger"
            ],

            "high": [
                "engine overheating",
                "engine is overheating",
                "engine very hot",
                "engine is very hot",
                "engine hot",
                "engine is hot",
                "overheating",
                "overheated engine",

                "coolant leak",
                "coolant is leaking",
                "coolant leaking",

                "steam from engine",
                "steam coming from engine",

                "tyre burst",
                "tire burst",
                "tyre puncture",
                "tire puncture",
                "flat tyre",
                "flat tire",

                "engine failure",
                "engine failed",
                "engine stopped",
                "engine suddenly stopped",
                "engine stalled"
            ],

            "medium": [
                "battery",
                "battery warning",
                "warning light",

                "electrical",
                "wiring",

                "fuel problem",
                "fuel issue",
                "out of fuel",
                "ran out of fuel",
                "run out of fuel"
            ]
        }

        # =========================================================
        # PROBLEM PRIORITY
        # =========================================================

        self.problem_priority = {

            "accident": 100,
            "brake_failure": 95,
            "engine_overheating": 90,
            "engine_failure": 80,
            "tyre_puncture": 70,
            "battery_failure": 60,
            "fuel_problem": 50,
            "electrical_failure": 40
        }

    # =============================================================
    # TEXT NORMALIZATION
    # =============================================================

    def normalize_text(self, text):

        if not text:
            return ""

        text = str(text)

        text = text.lower().strip()

        # Handle curly apostrophe
        text = text.replace("’", "'")

        # Normalize common contractions. Word boundaries matter: a plain
        # replace turned "significant" into "significan't".
        text = re.sub(r"\bdont\b", "don't", text)
        text = re.sub(r"\bcant\b", "can't", text)
        text = re.sub(r"\bwont\b", "won't", text)
        text = re.sub(r"\bdoesnt\b", "doesn't", text)
        text = re.sub(r"\bisnt\b", "isn't", text)

        # Keep apostrophe because of won't / can't
        text = re.sub(r"[^a-z0-9'\s]", " ", text)

        text = re.sub(r"\s+", " ", text)

        return text.strip()

    # =============================================================
    # EXACT PHRASE MATCH
    # =============================================================

    def _match(self, phrase, text):

        pattern = (
            r"(?<![a-z0-9])"
            + re.escape(phrase)
            + r"(?![a-z0-9])"
        )

        return re.search(pattern, text) is not None

    # =============================================================
    # NEGATION-AWARE MATCH
    # -------------------------------------------------------------
    # "no smoke", "not overheating", "no sign of fire" must not be
    # read as the hazard being present. Only negations directly in
    # front of the phrase count, so "not sure, maybe smoke" still
    # matches (the conservative choice for safety).
    # =============================================================

    def _is_negated(self, tokens, start):

        if start <= 0:
            return False

        previous = tokens[start - 1]

        if previous in _NEGATORS or previous in {"not", "isn't", "wasn't", "aren't", "weren't"}:
            return True

        window = " ".join(tokens[max(0, start - 3):start])

        if any(window.endswith(phrase) for phrase in _NEGATING_PHRASES):
            return True

        if " ".join(tokens[max(0, start - 2):start]) == "no longer":
            return True

        return False

    def _match_affirmed(self, phrase, text):
        """True when the phrase occurs at least once without a negation in front."""

        tokens = text.split()
        parts = phrase.split()
        size = len(parts)

        for index in range(len(tokens) - size + 1):

            if tokens[index:index + size] == parts and not self._is_negated(tokens, index):
                return True

        return False

    # =============================================================
    # SYMPTOM / HAZARD EXTRACTION (word-proximity layer)
    # =============================================================

    def _clauses(self, description):
        """Split free text into clauses so proximity never crosses sentences."""

        raw = str(description or "").lower().replace("’", "'")
        parts = re.split(r"[.;!?\n]+|,\s*but\s+|\bbut\b|\bhowever\b", raw)

        return [clause for clause in (self.normalize_text(p) for p in parts) if clause]

    @staticmethod
    def _spans(tokens, terms):

        spans = []

        for term in terms:
            words = term.split()
            size = len(words)
            for index in range(len(tokens) - size + 1):
                if tokens[index:index + size] == words:
                    spans.append((index, index + size - 1, term))

        return spans

    @staticmethod
    def _gap(first, second):
        """Words between two non-overlapping spans (None when they overlap)."""

        if first[1] < second[0]:
            return second[0] - first[1]

        if second[1] < first[0]:
            return first[0] - second[1]

        return None

    def extract_symptoms(self, description):
        """
        Return proximity evidence: a list of
        {problem, evidence, terms, weight} found in the description.
        """

        findings = []

        for clause in self._clauses(description):

            tokens = clause.split()

            for problem, group_a, group_b, window, weight, label in _PROXIMITY_RULES:

                spans_a = [s for s in self._spans(tokens, _TERMS[group_a]) if not self._is_negated(tokens, s[0])]
                spans_b = [s for s in self._spans(tokens, _TERMS[group_b]) if not self._is_negated(tokens, s[0])]

                hit = None

                for span_a in spans_a:
                    for span_b in spans_b:
                        gap = self._gap(span_a, span_b)
                        if gap is not None and gap <= window:
                            hit = (span_a[2], span_b[2])
                            break
                    if hit:
                        break

                if not hit:
                    continue

                # "hit the brakes" / "hit a pothole" are not collisions.
                if problem == "accident" and re.search(
                    r"\bhit (the )?(brake|brakes|pothole|a pothole|speed breaker|a speed breaker|bump|a bump)\b",
                    clause,
                ):
                    continue

                if not any(f["problem"] == problem and f["evidence"] == label for f in findings):
                    findings.append({
                        "problem": problem,
                        "evidence": label,
                        "terms": list(hit),
                        "weight": weight,
                    })

        return findings

    def detect_hazards(self, description):
        """Return hazards that are explicitly present (negation-aware)."""

        hazards = []
        text = self.normalize_text(description)

        for hazard, phrases in _HAZARDS.items():

            for phrase in phrases:

                if self._match_affirmed(phrase, text):
                    hazards.append({"hazard": hazard, "evidence": phrase})
                    break

        names = {h["hazard"] for h in hazards}

        # "burning smell" alone is not an open fire; keep the more specific hazard.
        if "burning_smell" in names and "fire" in names:
            fire = next(h for h in hazards if h["hazard"] == "fire")
            if fire["evidence"] == "burning":
                hazards = [h for h in hazards if h["hazard"] != "fire"]

        return hazards

    # =============================================================
    # DETECT PROBLEM
    # =============================================================

    def detect_problem(self, description):

        text = self.normalize_text(description)

        if not text:

            return {
                "problem": "unknown",
                "confidence": 0.0,
                "matched_keywords": [],
                "evidence": [],
                "evidence_source": "none",
                "ambiguous": False,
                "alternatives": [],
            }

        scores = {}

        matched_keywords = {}

        # ---------------------------------------------------------
        # Check every problem
        # ---------------------------------------------------------

        for problem, patterns in self.problem_patterns.items():

            matches = []

            for pattern in patterns:

                if self._match_affirmed(pattern, text):

                    matches.append(pattern)

            if matches:

                # Longer/more specific phrases receive more weight.
                score = 0

                for match in matches:

                    words = len(match.split())

                    score += 1.0 + (0.15 * max(words - 1, 0))

                scores[problem] = score

                matched_keywords[problem] = matches

        # ---------------------------------------------------------
        # Nothing detected by phrases; proximity evidence added below
        # ---------------------------------------------------------

        phrase_problems = set(scores)

        # ---------------------------------------------------------
        # Word-proximity evidence (free-form wording, any word order)
        # ---------------------------------------------------------

        proximity = self.extract_symptoms(description)
        proximity_by_problem = {}

        for finding in proximity:

            problem = finding["problem"]
            proximity_by_problem.setdefault(problem, []).append(finding["evidence"])
            scores[problem] = scores.get(problem, 0.0) + finding["weight"]

        # A fuel/petrol smell or leak is a hazard, not an empty tank:
        # never route it to fuel delivery unless the tank is explicitly empty.
        if (
            "fuel_problem" in scores
            and any(h["hazard"] == "fuel_leak" for h in self.detect_hazards(description))
            and not any(self._match_affirmed(p, text) for p in
                        ("out of fuel", "out of petrol", "ran out of fuel", "ran out of petrol",
                         "run out of fuel", "run out of petrol", "no fuel", "no petrol", "fuel empty"))
        ):
            scores.pop("fuel_problem", None)
            matched_keywords.pop("fuel_problem", None)
            proximity_by_problem.pop("fuel_problem", None)

        if not scores:

            return {
                "problem": "unknown",
                "confidence": 0.0,
                "matched_keywords": [],
                "evidence": [],
                "evidence_source": "none",
                "ambiguous": False,
                "alternatives": [],
            }

        # ---------------------------------------------------------
        # IMPORTANT CONFLICT RESOLUTION
        #
        # Example:
        #
        # "car suddenly stopped and engine is very hot"
        #
        # Both engine_failure and engine_overheating can match.
        # The overheating evidence is more specific, so overheating
        # must win.
        #
        # Order of specific overrides (most dangerous first):
        #   accident > brake_failure > engine_overheating
        # Previously overheating was checked first, so
        # "my car crashed and smoke is coming from the engine" was
        # classified as overheating and routed to a mechanic instead
        # of the accident/emergency workflow.
        # ---------------------------------------------------------

        overheating_words = [
            "engine overheating",
            "engine is overheating",
            "engine very hot",
            "engine is very hot",
            "engine hot",
            "engine is hot",
            "overheating",
            "overheated engine",
            "coolant leak",
            "coolant is leaking",
            "coolant leaking",
            "steam from engine",
            "steam coming from engine",
            "smoke from engine",
            "smoke coming from engine"
        ]

        brake_words = [
            "brakes failed",
            "brakes have failed",
            "brakes completely failed",
            "brakes have completely failed",
            "brake failure",
            "brake failed",
            "brakes not working",
            "brakes are not working",
            "cannot brake",
            "can't brake",
            "cannot stop",
            "can't stop",
            "car won't stop",
            "car will not stop",
            "vehicle won't stop",
            "vehicle will not stop"
        ]

        accident_words = [
            "accident",
            "crash",
            "crashed",
            "collision",
            "collided",
            "hit another car",
            "hit another vehicle"
        ]

        def specific(problem, words):
            return problem in scores and (
                any(self._match_affirmed(word, text) for word in words)
                or problem in proximity_by_problem
            )

        override = True

        if specific("accident", accident_words):

            best_problem = "accident"

        elif specific("brake_failure", brake_words):

            best_problem = "brake_failure"

        elif specific("engine_overheating", overheating_words):

            best_problem = "engine_overheating"

        else:

            override = False

            # Add priority to resolve ties.
            weighted_scores = {}

            for problem, score in scores.items():

                priority = self.problem_priority.get(
                    problem,
                    0
                )

                weighted_scores[problem] = (
                    score * 100
                ) + priority

            best_problem = max(
                weighted_scores,
                key=weighted_scores.get
            )

        # ---------------------------------------------------------
        # AMBIGUITY
        # Two different problems with similar evidence and no
        # specific override → ask the driver follow-up questions.
        # ---------------------------------------------------------

        alternatives = sorted(
            (p for p in scores if p != best_problem),
            key=lambda p: scores[p],
            reverse=True,
        )

        ambiguous = bool(
            not override
            and alternatives
            and scores[alternatives[0]] >= 0.75 * scores[best_problem]
        )

        # ---------------------------------------------------------
        # CONFIDENCE (heuristic match strength, see CONFIDENCE_BASIS)
        # ---------------------------------------------------------

        matches = matched_keywords.get(best_problem, [])

        match_count = len(matches)

        if best_problem in phrase_problems:

            total_patterns = len(
                self.problem_patterns[best_problem]
            )

            coverage = (
                match_count /
                max(total_patterns, 1)
            )

            confidence = 0.60 + (
                min(coverage, 0.80) * 0.40
            )

            # Multiple matching phrases increase confidence.
            if match_count >= 2:

                confidence += 0.04

            if match_count >= 3:

                confidence += 0.03

            if best_problem in proximity_by_problem:

                confidence += 0.03

            evidence_source = "phrase"

        else:

            # Only free-form word-proximity evidence: deliberately lower.
            supporting = len(proximity_by_problem.get(best_problem, []))
            confidence = 0.45 + 0.05 * max(supporting - 1, 0)
            confidence = min(confidence, 0.60)
            evidence_source = "symptom_proximity"

        if ambiguous:

            confidence = min(confidence, 0.55)

        confidence = min(
            confidence,
            0.99
        )

        evidence = list(matches) + [
            e for e in proximity_by_problem.get(best_problem, []) if e not in matches
        ]

        return {

            "problem": best_problem,

            "confidence": round(
                confidence,
                2
            ),

            "matched_keywords": matches or proximity_by_problem.get(best_problem, []),

            "evidence": evidence,

            "evidence_source": evidence_source,

            "ambiguous": ambiguous,

            "alternatives": alternatives[:3],
        }

    # =============================================================
    # DETERMINE SEVERITY
    # =============================================================

    def determine_severity(
        self,
        description,
        problem,
        hazards=None
    ):

        text = self.normalize_text(description)

        if hazards is None:
            hazards = self.detect_hazards(description)

        hazard_names = {h["hazard"] for h in hazards}

        # ---------------------------------------------------------
        # Explicit, non-negated life-safety hazards
        # ---------------------------------------------------------

        if hazard_names & {"fire", "smoke", "fuel_leak", "injury", "brake_loss"}:

            return "CRITICAL"

        # ---------------------------------------------------------
        # Critical keywords first (negation-aware: "no smoke" is not smoke)
        # ---------------------------------------------------------

        for keyword in self.severity_rules["critical"]:

            if self._match_affirmed(keyword, text):

                return "CRITICAL"

        # ---------------------------------------------------------
        # Problem-specific severity
        # ---------------------------------------------------------

        if problem == "accident":

            return "CRITICAL"

        if problem == "brake_failure":

            return "CRITICAL"

        if problem == "engine_overheating":

            return "HIGH"

        if problem == "engine_failure":

            return "HIGH"

        if problem == "tyre_puncture":

            return "HIGH"

        if hazard_names & {"steam", "burning_smell"}:

            return "HIGH"

        # ---------------------------------------------------------
        # High severity keywords
        # ---------------------------------------------------------

        for keyword in self.severity_rules["high"]:

            if self._match_affirmed(keyword, text):

                return "HIGH"

        # ---------------------------------------------------------
        # Medium severity keywords
        # ---------------------------------------------------------

        for keyword in self.severity_rules["medium"]:

            if self._match_affirmed(keyword, text):

                return "MEDIUM"

        # Problem-level fallback for detected problems without keywords
        if problem in {"battery_failure", "fuel_problem", "electrical_failure"}:

            return "MEDIUM"

        return "LOW"

    # =============================================================
    # SAFETY DECISION
    # =============================================================

    def determine_safety(
        self,
        problem,
        severity,
        description,
        hazards=None
    ):

        text = self.normalize_text(description)

        # Critical and high severity incidents are unsafe.
        if severity in {
            "CRITICAL",
            "HIGH"
        }:

            return False

        if hazards is None:
            hazards = self.detect_hazards(description)

        if hazards:

            return False

        dangerous_conditions = [

            "smoke",
            "fire",
            "flames",
            "explosion",

            "fuel leak",
            "petrol leak",
            "gas leak",

            "brakes failed",
            "brakes have failed",
            "brake failure",

            "cannot stop",
            "can't stop",
            "car won't stop",
            "car will not stop",

            "accident",
            "crash",
            "collision",

            "engine overheating",
            "engine is overheating",
            "engine very hot",
            "engine is very hot",
            "overheating",

            "tyre burst",
            "tire burst",
            "flat tyre",
            "flat tire"
        ]

        for condition in dangerous_conditions:

            if self._match_affirmed(
                condition,
                text
            ):

                return False

        # Problem-level safety fallback.
        if problem in {
            "brake_failure",
            "engine_overheating",
            "engine_failure",
            "tyre_puncture",
            "accident"
        }:

            return False

        # Nothing identified: we cannot claim the vehicle is safe to drive.
        if problem == "unknown":

            return False

        return True

    # =============================================================
    # RECOMMENDED ACTION
    # =============================================================

    def determine_action(
        self,
        problem,
        severity,
        safe_to_drive
    ):

        actions = {

            "engine_overheating": (
                "Stop driving immediately. "
                "Move to a safe location, switch off the engine, "
                "stay away from steam or smoke, and request "
                "roadside assistance."
            ),

            "brake_failure": (
                "Do not continue driving. "
                "If possible, bring the vehicle to a safe location "
                "without putting yourself or others at risk and "
                "request emergency roadside assistance."
            ),

            "tyre_puncture": (
                "Slow down safely and move to a safe location. "
                "Do not continue driving on a severely damaged or "
                "flat tyre. Request tyre or roadside assistance."
            ),

            "battery_failure": (
                "Move to a safe location and request battery "
                "jump-start or roadside assistance."
            ),

            "engine_failure": (
                "Move to a safe location if possible, "
                "switch on hazard lights, and request "
                "roadside assistance."
            ),

            "accident": (
                "Move to a safe location if possible, "
                "check for injuries, and contact emergency "
                "services or roadside assistance."
            ),

            "fuel_problem": (
                "Move to a safe location and request fuel "
                "delivery or roadside assistance."
            ),

            "electrical_failure": (
                "Stop in a safe location and request vehicle "
                "inspection or roadside assistance."
            )
        }

        if problem in actions:

            return actions[problem]

        return (
            "No specific vehicle problem was detected. "
            "Move to a safe location if necessary and seek "
            "professional diagnosis."
        )

    # =============================================================
    # ASSISTANCE TYPE
    # =============================================================

    def determine_assistance(
        self,
        problem,
        severity
    ):

        assistance_map = {

            "tyre_puncture":
                "tyre_assistance",

            "battery_failure":
                "battery_assistance",

            "fuel_problem":
                "fuel_delivery",

            "engine_overheating":
                "mechanic_or_roadside_assistance",

            "brake_failure":
                "emergency_roadside_assistance",

            "accident":
                "emergency_services",

            "engine_failure":
                "mechanic_or_roadside_assistance",

            "electrical_failure":
                "electrical_vehicle_assistance"
        }

        if problem in assistance_map:

            return assistance_map[problem]

        if severity == "CRITICAL":

            return "emergency_roadside_assistance"

        return "general_roadside_assistance"
    # =============================================================
    # COMPLETE ANALYSIS
    # =============================================================

    def follow_up_questions(self, problem, ambiguous=False, alternatives=(), evidence_source="phrase"):
        """Questions that would let the driver clarify an unclear report."""

        if problem == "unknown":
            return list(FOLLOW_UP_QUESTIONS["general"])

        questions = []

        if ambiguous:
            for candidate in [problem, *alternatives[:1]]:
                questions.extend(FOLLOW_UP_QUESTIONS.get(candidate, [])[:1])
            questions.append("Is anyone injured, or is there smoke, steam, flames or a fuel smell?")
        elif evidence_source in ("symptom_proximity", "ml"):
            questions.extend(FOLLOW_UP_QUESTIONS.get(problem, [])[:2])

        return questions

    # =============================================================
    # MACHINE-LEARNING SECOND OPINION
    # =============================================================

    def ml_predict(self, description):
        """Both ML models' prediction, or None when ML is switched off."""

        if not self.use_ml or get_incident_models is None:
            return None
        try:
            models = self._ml_models or get_incident_models()
            return models.predict(description)
        except Exception as error:  # noqa: BLE001 - never break the analysis
            return {"available": False, "reason": f"{error.__class__.__name__}: {error}"}

    # Fusion thresholds (chosen by cross-validation in ml/train_incident_models.py and
    # stored with the models; these defaults are used if no value was saved).
    DEFAULT_FUSION = {"agree_min": 0.55, "alone_min": 0.80, "override_min": 0.85}
    # Types the ML may add but never take away: a rule decision of accident or
    # brake failure is kept even if the ML disagrees (safety first).
    SAFETY_CRITICAL = ("accident", "brake_failure")

    def combine_with_ml(self, detected, ml, hazards):
        """
        Hybrid decision for the incident TYPE (hazards and severity stay rule-based).

        1. Rules matched a specific phrase            -> the rules decide; ML is shown as a check.
        2. Rules found several close problems         -> ML picks among those candidates.
        3. Rules found nothing                        -> ML decides if Logistic Regression is very
           confident, or confident and confirmed by the Random Forest; "other" stays unknown.
        4. Rules only had weak word-proximity evidence -> a confident ML result may replace
           it, except that accident and brake failure are never replaced.
        Safety guard: a fuel smell/leak is never turned into "out of fuel".

        Returns (problem, decision_source).
        """

        rules_problem = detected["problem"]
        if not ml or not ml.get("available"):
            return rules_problem, ("rules" if rules_problem != "unknown" else "none")

        fusion = {**self.DEFAULT_FUSION, **(ml.get("fusion") or {})}
        lr, rf = ml["logistic_regression"], ml["random_forest"]
        lr_label, lr_p = lr["problem"], lr["probability"]
        hazard_names = {h["hazard"] for h in hazards}

        def allowed(problem):
            return (problem in SUPPORTED_PROBLEMS and problem != ML_OTHER
                    and not (problem == "fuel_problem" and "fuel_leak" in hazard_names))

        def ml_decides():
            return allowed(lr_label) and (lr_p >= fusion["alone_min"]
                                          or (rf["problem"] == lr_label and lr_p >= fusion["agree_min"]))

        if rules_problem == "unknown":
            return (lr_label, "ml") if ml_decides() else ("unknown", "none")

        if detected.get("ambiguous"):
            candidates = [rules_problem, *detected.get("alternatives", [])]
            probabilities = lr.get("probabilities", {})
            best = max(candidates, key=lambda c: probabilities.get(c, 0.0))
            if best != rules_problem and probabilities.get(best, 0.0) >= fusion["agree_min"] and allowed(best):
                return best, "rules+ml"
            return rules_problem, "rules"

        if (detected.get("evidence_source") == "symptom_proximity" and rules_problem not in self.SAFETY_CRITICAL
                and lr_label != rules_problem and allowed(lr_label) and lr_p >= fusion["override_min"]):
            return lr_label, "ml"

        return rules_problem, "rules"

    def analyze(self, description, problem_override=None):
        """
        Analyze a free-text incident description.

        ``problem_override`` lets a driver confirm/correct the incident type.
        Severity and hazards are still computed from the description, so a
        correction can never hide smoke, fire, a fuel leak or an injury.

        Backward compatible: the original keys (problem, confidence, severity,
        safe_to_drive, recommended_action, assistance_type, matched_keywords)
        are unchanged in meaning; new keys are additive.
        """

        description = "" if description is None else str(description)
        stripped = description.strip()

        if not stripped:
            input_quality = "empty"
        elif len(stripped) < 5 or len(self.normalize_text(stripped).split()) < 2:
            input_quality = "too_short"
        else:
            input_quality = "ok"

        detected = self.detect_problem(
            description
        )

        hazards = self.detect_hazards(description)

        # Machine-learning second opinion on the incident TYPE (only for real text).
        ml = self.ml_predict(description) if input_quality == "ok" else None
        ai_problem, decision_source = self.combine_with_ml(detected, ml, hazards)
        if ml and ml.get("available"):
            for key in ("logistic_regression", "random_forest"):
                ml[key]["label"] = PROBLEM_LABELS.get(ml[key]["problem"], "Other (not a roadside breakdown type)")
            ml["agrees_with_rules"] = ml["logistic_regression"]["problem"] == (
                detected["problem"] if detected["problem"] != "unknown" else ML_OTHER)
            ml["rules_problem"] = detected["problem"]

        problem = ai_problem
        driver_corrected = False

        if problem_override:
            override = str(problem_override).strip().lower()
            if override in SUPPORTED_PROBLEMS and override != ai_problem:
                problem = override
                driver_corrected = True

        confidence = detected["confidence"]
        confidence_basis = CONFIDENCE_BASIS
        evidence = list(detected.get("evidence", []))
        evidence_source = detected.get("evidence_source", "none")

        if decision_source == "ml":
            confidence = round(ml["logistic_regression"]["probability"], 2)
            confidence_basis = ML_CONFIDENCE_BASIS
            evidence = [f"ML words: {', '.join(ml['logistic_regression']['top_words'])}"] if ml["logistic_regression"]["top_words"] else []
            evidence_source = "ml"

        severity = self.determine_severity(
            description,
            problem,
            hazards
        )

        safe_to_drive = self.determine_safety(
            problem,
            severity,
            description,
            hazards
        )

        recommended_action = self.determine_action(
            problem,
            severity,
            safe_to_drive
        )

        assistance_type = self.determine_assistance(
            problem,
            severity
        )

        if not safe_to_drive:
            safety_assessment = "UNSAFE" if (problem != "unknown" or hazards or severity in {"CRITICAL", "HIGH"}) else "NOT_CONFIRMED"
        else:
            safety_assessment = "LIKELY_SAFE_WITH_CAUTION"

        follow_up = self.follow_up_questions(
            ai_problem,
            detected.get("ambiguous", False),
            [a for a in detected.get("alternatives", []) if a != ai_problem] + ([detected["problem"]] if decision_source == "rules+ml" else []),
            evidence_source,
        ) if not driver_corrected else []

        return {

            "problem":
                problem,

            "confidence":
                confidence,

            "severity":
                severity,

            "safe_to_drive":
                safe_to_drive,

            "recommended_action":
                recommended_action,

            "assistance_type":
                assistance_type,

            "matched_keywords":
                detected["matched_keywords"],

            # ----- additive structured fields -----
            "problem_label": PROBLEM_LABELS.get(problem, problem.replace("_", " ").title()),
            "ai_problem": ai_problem,
            "driver_corrected": driver_corrected,
            "is_prediction": True,
            "confidence_basis": confidence_basis,
            "evidence": evidence,
            "evidence_source": evidence_source,
            "decision_source": decision_source,
            "ml": ml,
            "hazards": hazards,
            "ambiguous": detected.get("ambiguous", False),
            "alternatives": detected.get("alternatives", []),
            "needs_clarification": bool(follow_up) and (ai_problem == "unknown" or detected.get("ambiguous", False) or evidence_source in ("symptom_proximity", "ml")),
            "follow_up_questions": follow_up,
            "safety_assessment": safety_assessment,
            "input_quality": input_quality,
        }


# =============================================================
# TEST SUITE
# =============================================================

def run_tests():

    analyzer = IncidentAnalyzer()

    tests = [

        (
            "ENGINE OVERHEATING",
            "My car suddenly stopped and the engine is very hot with smoke coming from the engine.",
            "engine_overheating"
        ),

        (
            "BRAKE FAILURE",
            "My brakes have completely failed and the car won't stop.",
            "brake_failure"
        ),

        (
            "TYRE PUNCTURE",
            "I have a flat tyre and my car is shaking.",
            "tyre_puncture"
        ),

        (
            "BATTERY FAILURE",
            "My battery is dead and the car won't start.",
            "battery_failure"
        ),

        (
            "ACCIDENT",
            "I was involved in a collision and my car is badly damaged.",
            "accident"
        ),

        (
            "FUEL PROBLEM",
            "My car has run out of fuel and stopped.",
            "fuel_problem"
        ),

        (
            "ELECTRICAL FAILURE",
            "The dashboard went blank and the electrical system stopped.",
            "electrical_failure"
        ),

        (
            "ENGINE FAILURE",
            "The engine suddenly stopped while I was driving.",
            "engine_failure"
        ),

        (
            "UNKNOWN",
            "My car is making a strange sound.",
            "unknown"
        )
    ]

    passed = 0

    failed = 0

    print()

    print("=" * 75)

    print(
        "RSA AI INCIDENT ANALYZER - TEST SUITE"
    )

    print("=" * 75)

    for name, description, expected in tests:

        try:

            result = analyzer.analyze(
                description
            )

            actual = result["problem"]

            status = (
                "PASS"
                if actual == expected
                else "FAIL"
            )

            if status == "PASS":

                passed += 1

            else:

                failed += 1

            print()

            print("-" * 75)

            print(
                f"TEST              : {name}"
            )

            print(
                f"STATUS            : {status}"
            )

            print(
                f"Expected Problem  : {expected}"
            )

            print(
                f"Actual Problem    : {actual}"
            )

            print(
                f"Confidence        : {result['confidence']}"
            )

            print(
                f"Severity          : {result['severity']}"
            )

            print(
                f"Safe To Drive     : {result['safe_to_drive']}"
            )

            print(
                f"Assistance Type   : {result['assistance_type']}"
            )

            print(
                f"Matched Keywords  : {result['matched_keywords']}"
            )

            print(
                "Recommended Action:"
            )

            print(
                f"  {result['recommended_action']}"
            )

        except Exception as error:

            failed += 1

            print()

            print("-" * 75)

            print(
                f"TEST              : {name}"
            )

            print(
                "STATUS            : ERROR"
            )

            print(
                f"ERROR             : {error}"
            )

    print()

    print("=" * 75)

    print(
        "RSA AI TEST RESULTS"
    )

    print("=" * 75)

    print(
        f"TOTAL TESTS       : {len(tests)}"
    )

    print(
        f"PASSED            : {passed}"
    )

    print(
        f"FAILED            : {failed}"
    )

    print("=" * 75)

    if failed == 0:

        print(
            "ALL TESTS PASSED"
        )

        print(
            "RSA INCIDENT ANALYZER IS WORKING CORRECTLY"
        )

    else:

        print(
            "SOME TESTS FAILED"
        )

    print("=" * 75)


# =============================================================
# RUN
# =============================================================

if __name__ == "__main__":

    run_tests()