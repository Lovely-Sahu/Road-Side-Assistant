"""
RSA machine-learning incident classifiers
=========================================

Two text classifiers predict the incident type from the driver's description:

* TF-IDF + Logistic Regression  - the main ML model (gives a probability and the
  words that pushed the decision, so every prediction can be explained).
* TF-IDF + Random Forest        - a second, independent opinion (many decision
  trees voting).

TF-IDF turns the description into numbers: each word / two-word phrase gets a
weight that is high when the word is frequent in this description but rare in
the dataset ("smoke", "puncture") and low for common words ("my", "the").

The models only suggest the incident TYPE. Hazards, severity and the
safe-to-drive decision always stay with the rule engine
(ai/incident_analyzer.py), so a wrong ML guess can never hide smoke, fire, a
fuel leak, an injury or brake failure.

The app keeps working without scikit-learn: the analyzer then uses the rules
only. Saved models are re-trained automatically from the CSV dataset when they
are missing or were saved by a different scikit-learn version.

Train / evaluate:  python -m ml.train_incident_models
"""

import csv
import json
import logging
import os
import threading
from pathlib import Path

logger = logging.getLogger("rsa.ml")

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "datasets"
TRAIN_CSV = DATA_DIR / "incidents_train.csv"
TEST_CSV = DATA_DIR / "incidents_test.csv"
MODEL_DIR = BASE_DIR / "models"
LR_FILE = MODEL_DIR / "incident_tfidf_logreg.joblib"
RF_FILE = MODEL_DIR / "incident_tfidf_random_forest.joblib"
META_FILE = MODEL_DIR / "incident_models_meta.json"

OTHER = "other"  # problems RSA does not dispatch (AC, locks, keys, cosmetic damage ...)
LABELS = (
    "engine_overheating", "brake_failure", "tyre_puncture", "battery_failure",
    "engine_failure", "accident", "fuel_problem", "electrical_failure", OTHER,
)

# Defaults; train_incident_models.py chooses the final values by cross-validation
# and stores them in the meta file.
DEFAULT_PARAMS = {"logreg_C": 10.0, "rf_n_estimators": 300, "rf_max_depth": None}


def ml_enabled():
    return os.environ.get("RSA_ML_ENABLED", "1").strip().lower() not in {"0", "false", "no", "off"}


def load_dataset(path):
    """Return (texts, labels, groups) from a dataset CSV."""
    texts, labels, groups = [], [], []
    with Path(path).open(encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            texts.append(row["text"])
            labels.append(row["label"])
            groups.append(int(row.get("group") or len(groups) + 1))
    return texts, labels, groups


def build_pipelines(params=None):
    """The two TF-IDF pipelines (imports scikit-learn lazily)."""
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import Pipeline

    p = {**DEFAULT_PARAMS, **(params or {})}

    def tfidf():
        # Words and two-word phrases ("not starting", "no petrol"); sublinear TF
        # stops a repeated word from dominating; accents normalised.
        return TfidfVectorizer(ngram_range=(1, 2), sublinear_tf=True, strip_accents="unicode", lowercase=True)

    logreg = Pipeline([
        ("tfidf", tfidf()),
        ("clf", LogisticRegression(C=p["logreg_C"], max_iter=5000, class_weight="balanced")),
    ])
    forest = Pipeline([
        ("tfidf", tfidf()),
        ("clf", RandomForestClassifier(n_estimators=int(p["rf_n_estimators"]), max_depth=p["rf_max_depth"],
                                       class_weight="balanced_subsample", random_state=42, n_jobs=1)),
    ])
    return logreg, forest


class IncidentModels:
    """Lazy-loaded pair of trained models. Thread-safe; one shared instance."""

    def __init__(self, model_dir=None, train_csv=None):
        self.model_dir = Path(model_dir) if model_dir else MODEL_DIR
        self.train_csv = Path(train_csv) if train_csv else TRAIN_CSV
        self._lock = threading.Lock()
        self._loaded = False
        self.available = False
        self.reason = None
        self.logreg = None
        self.forest = None
        self.meta = {}

    # ------------------------------------------------------------ loading
    @property
    def lr_file(self):
        return self.model_dir / LR_FILE.name

    @property
    def rf_file(self):
        return self.model_dir / RF_FILE.name

    @property
    def meta_file(self):
        return self.model_dir / META_FILE.name

    def ensure_loaded(self):
        if self._loaded:
            return self.available
        with self._lock:
            if self._loaded:
                return self.available
            try:
                self._load_or_train()
            except Exception as error:  # noqa: BLE001 - the rules keep working
                self.available = False
                self.reason = f"ML models unavailable: {error.__class__.__name__}: {error}"
                logger.warning(self.reason)
            self._loaded = True
        return self.available

    def _load_or_train(self):
        if not ml_enabled():
            self.reason = "ML disabled (RSA_ML_ENABLED=0)"
            return
        try:
            import joblib
            import sklearn
        except ImportError:
            self.reason = "scikit-learn is not installed (pip install scikit-learn); using rules only"
            logger.warning(self.reason)
            return

        meta = {}
        if self.meta_file.exists():
            try:
                meta = json.loads(self.meta_file.read_text(encoding="utf-8"))
            except ValueError:
                meta = {}

        same_version = meta.get("sklearn_version") == sklearn.__version__
        if same_version and self.lr_file.exists() and self.rf_file.exists():
            try:
                self.logreg = joblib.load(self.lr_file)
                self.forest = joblib.load(self.rf_file)
                self.meta = meta
                self.available = True
                return
            except Exception as error:  # noqa: BLE001 - fall through to re-training
                logger.warning("Could not load saved ML models (%s); re-training.", error)

        # Missing, or saved by another scikit-learn version: re-train from the dataset (takes seconds).
        if not self.train_csv.exists():
            self.reason = f"training data not found: {self.train_csv}"
            return
        self.meta = meta
        self.train(params=meta.get("params"), save=True, fusion=meta.get("fusion"))

    def train(self, params=None, save=True, fusion=None):
        """Fit both pipelines on the training CSV; optionally save them."""
        import sklearn

        texts, labels, _ = load_dataset(self.train_csv)
        logreg, forest = build_pipelines(params)
        logreg.fit(texts, labels)
        forest.fit(texts, labels)
        self.logreg, self.forest = logreg, forest
        self.meta = {
            "sklearn_version": sklearn.__version__,
            "params": {**DEFAULT_PARAMS, **(params or {})},
            "trained_on": len(texts),
            "labels": sorted(set(labels)),
            "dataset": self.train_csv.name,
            "fusion": fusion or self.meta.get("fusion"),
        }
        self.available = True
        self.reason = None
        if save:
            try:
                import joblib
                self.model_dir.mkdir(parents=True, exist_ok=True)
                joblib.dump(logreg, self.lr_file, compress=3)
                joblib.dump(forest, self.rf_file, compress=3)
                self.meta_file.write_text(json.dumps(self.meta, indent=2), encoding="utf-8")
            except OSError as error:
                logger.warning("Trained ML models could not be saved (%s); they stay in memory.", error)
        return self

    # ------------------------------------------------------------ prediction
    @staticmethod
    def _top_words(pipeline, text, label, limit=4):
        """Words in this description that pushed Logistic Regression towards ``label``."""
        vectorizer = pipeline.named_steps["tfidf"]
        clf = pipeline.named_steps["clf"]
        row = vectorizer.transform([text])
        if label not in list(clf.classes_):
            return []
        from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS

        coef = clf.coef_[list(clf.classes_).index(label)]
        names = vectorizer.get_feature_names_out()
        contributions = [(float(row[0, j] * coef[j]), names[j]) for j in row.nonzero()[1]]
        # Only for display: skip features made of filler words ("got", "on the"); the model
        # itself keeps them, because words like "no" and "not" matter for meaning.
        filler = ENGLISH_STOP_WORDS | {"got", "get", "went", "near", "just", "suddenly", "really", "also", "ka", "ho"}
        shown, words_shown = [], set()
        for score, name in sorted(contributions, reverse=True):
            content = [w for w in name.split() if w not in filler]
            if score <= 0 or not content or set(content) <= words_shown:
                continue
            shown.append(" ".join(content) if len(content) == 1 else name)
            words_shown.update(content)
            if len(shown) == limit:
                break
        return shown

    def predict(self, text):
        """
        Predict the incident type with both models.

        Returns ``{"available": False, "reason": ...}`` when ML cannot be used,
        otherwise both models' label, probability and the top words.
        """
        if not self.ensure_loaded():
            return {"available": False, "reason": self.reason}
        text = str(text or "")
        lr_proba = self.logreg.predict_proba([text])[0]
        rf_proba = self.forest.predict_proba([text])[0]
        lr_classes = [str(c) for c in self.logreg.classes_]
        rf_classes = [str(c) for c in self.forest.classes_]
        lr_best = max(range(len(lr_proba)), key=lambda i: lr_proba[i])
        rf_best = max(range(len(rf_proba)), key=lambda i: rf_proba[i])
        lr_label, rf_label = lr_classes[lr_best], rf_classes[rf_best]
        return {
            "available": True,
            "logistic_regression": {
                "problem": lr_label,
                "probability": round(float(lr_proba[lr_best]), 3),
                "probabilities": {c: round(float(p), 3) for c, p in zip(lr_classes, lr_proba)},
                "top_words": self._top_words(self.logreg, text, lr_label),
            },
            "random_forest": {
                "problem": rf_label,
                "probability": round(float(rf_proba[rf_best]), 3),
            },
            "models_agree": lr_label == rf_label,
            "trained_on": self.meta.get("trained_on"),
            "fusion": self.meta.get("fusion"),
        }


_shared = None
_shared_lock = threading.Lock()


def get_incident_models():
    """The shared model instance used by the analyzer and the web app."""
    global _shared
    if _shared is None:
        with _shared_lock:
            if _shared is None:
                _shared = IncidentModels()
    return _shared
