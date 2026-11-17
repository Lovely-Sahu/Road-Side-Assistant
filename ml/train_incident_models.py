"""
Train and evaluate the RSA incident classifiers.

    python -m ml.train_incident_models

1. Chooses hyper-parameters with 5-fold cross-validation on the TRAINING set only.
   Folds are grouped by sentence, so a sentence and its context variants never sit
   in different folds (no leakage). The thresholds for combining rules and ML are
   also chosen on out-of-fold predictions of the training set.
2. Trains TF-IDF + Logistic Regression and TF-IDF + Random Forest on all training data
   and saves them in ml/models/.
3. Evaluates on the separate TEST set (never used for training or tuning):
   the rule engine alone, each ML model alone, and the hybrid (rules + ML) analyzer.
4. Writes ml/evaluation/incident_models_report.json and confusion-matrix images.
"""

import json
import logging
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ml.incident_models import (  # noqa: E402
    LABELS, OTHER, TEST_CSV, TRAIN_CSV, IncidentModels, build_pipelines, load_dataset,
)

EVAL_DIR = Path(__file__).resolve().parent / "evaluation"
REPORT_FILE = EVAL_DIR / "incident_models_report.json"


def metrics(y_true, y_pred):
    from sklearn.metrics import accuracy_score, precision_recall_fscore_support

    precision, recall, f1, _ = precision_recall_fscore_support(y_true, y_pred, labels=list(LABELS),
                                                               average="macro", zero_division=0)
    return {"accuracy": round(accuracy_score(y_true, y_pred), 4), "precision_macro": round(precision, 4),
            "recall_macro": round(recall, 4), "f1_macro": round(f1, 4)}


def tune(texts, labels, groups):
    """Grid search with grouped, stratified 5-fold cross-validation (macro F1)."""
    from sklearn.model_selection import GridSearchCV, StratifiedGroupKFold

    cv = StratifiedGroupKFold(n_splits=5, shuffle=True, random_state=42)
    logreg, forest = build_pipelines()
    lr_search = GridSearchCV(logreg, {"clf__C": [0.3, 1, 3, 10, 30, 100]}, cv=cv, scoring="f1_macro", n_jobs=1)
    lr_search.fit(texts, labels, groups=groups)
    rf_search = GridSearchCV(forest, {"clf__n_estimators": [200, 400], "clf__max_depth": [None, 40]},
                             cv=cv, scoring="f1_macro", n_jobs=1)
    rf_search.fit(texts, labels, groups=groups)
    params = {"logreg_C": lr_search.best_params_["clf__C"],
              "rf_n_estimators": rf_search.best_params_["clf__n_estimators"],
              "rf_max_depth": rf_search.best_params_["clf__max_depth"]}
    return params, cv


def cross_validated(texts, labels, groups, params, cv):
    from sklearn.model_selection import cross_validate

    out = {}
    for name, pipe in zip(("logistic_regression", "random_forest"), build_pipelines(params)):
        scores = cross_validate(pipe, texts, labels, groups=groups, cv=cv, scoring=["accuracy", "f1_macro"], n_jobs=1)
        out[name] = {
            "accuracy_mean": round(float(scores["test_accuracy"].mean()), 4),
            "accuracy_std": round(float(scores["test_accuracy"].std()), 4),
            "f1_macro_mean": round(float(scores["test_f1_macro"].mean()), 4),
            "f1_macro_std": round(float(scores["test_f1_macro"].std()), 4),
        }
    return out


def out_of_fold(texts, labels, groups, params, cv):
    """Out-of-fold ML predictions for every training row (each predicted by models that never saw it)."""
    import numpy as np

    preds = [None] * len(texts)
    for train_idx, val_idx in cv.split(texts, labels, groups):
        logreg, forest = build_pipelines(params)
        tx = [texts[i] for i in train_idx]; ty = [labels[i] for i in train_idx]
        logreg.fit(tx, ty); forest.fit(tx, ty)
        vx = [texts[i] for i in val_idx]
        lr_p, rf_p = logreg.predict_proba(vx), forest.predict_proba(vx)
        for k, i in enumerate(val_idx):
            lb, rb = int(np.argmax(lr_p[k])), int(np.argmax(rf_p[k]))
            preds[i] = {"available": True,
                        "logistic_regression": {"problem": str(logreg.classes_[lb]), "probability": float(lr_p[k][lb]),
                                                "probabilities": {str(c): float(v) for c, v in zip(logreg.classes_, lr_p[k])},
                                                "top_words": []},
                        "random_forest": {"problem": str(forest.classes_[rb]), "probability": float(rf_p[k][rb])}}
    return preds


def tune_fusion(texts, labels, oof):
    """Pick the rules+ML combination thresholds that give the best macro F1 on out-of-fold predictions."""
    from sklearn.metrics import f1_score
    from ai.incident_analyzer import IncidentAnalyzer

    analyzer = IncidentAnalyzer(use_ml=False)
    cached = [(analyzer.detect_problem(t), analyzer.detect_hazards(t)) for t in texts]
    best = None
    # Design rule: the ML must think its answer is more likely than not (probability >= 0.5).
    for agree in (0.5, 0.6, 0.7, 0.8):
        for alone in (0.6, 0.7, 0.8, 0.9, 1.01):
            for override in (0.6, 0.7, 0.8, 0.9, 1.01):
                fusion = {"agree_min": agree, "alone_min": alone, "override_min": override}
                pred = []
                for (detected, hazards), ml in zip(cached, oof):
                    problem, _ = analyzer.combine_with_ml(detected, {**ml, "fusion": fusion}, hazards)
                    pred.append(OTHER if problem == "unknown" else problem)
                f1 = f1_score(labels, pred, labels=list(LABELS), average="macro", zero_division=0)
                key = (round(f1, 4), alone, override, agree)  # ties -> the more cautious thresholds
                if best is None or key > best[0]:
                    best = (key, fusion)
    (f1, *_), fusion = best
    return fusion, f1


def save_confusion(y_true, y_pred, title, path):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from sklearn.metrics import ConfusionMatrixDisplay
    except ImportError:
        return None
    short = {"engine_overheating": "Overheat", "brake_failure": "Brake", "tyre_puncture": "Tyre",
             "battery_failure": "Battery", "engine_failure": "Engine stop", "accident": "Accident",
             "fuel_problem": "Fuel", "electrical_failure": "Electrical", OTHER: "Other"}
    fig, ax = plt.subplots(figsize=(7.2, 6.2))
    ConfusionMatrixDisplay.from_predictions(y_true, y_pred, labels=list(LABELS),
                                            display_labels=[short[x] for x in LABELS],
                                            cmap="Blues", colorbar=False, ax=ax)
    ax.set_title(title, fontsize=11)
    ax.set_xlabel("Predicted type"); ax.set_ylabel("True type")
    plt.setp(ax.get_xticklabels(), rotation=40, ha="right")
    fig.tight_layout()
    fig.savefig(path, dpi=200)
    plt.close(fig)
    return path.name


def main():
    logging.disable(logging.WARNING)
    from sklearn.metrics import classification_report, confusion_matrix
    import sklearn

    started = time.time()
    train_x, train_y, groups = load_dataset(TRAIN_CSV)
    test_x, test_y, _ = load_dataset(TEST_CSV)
    print(f"Training rows: {len(train_x)}  |  test rows: {len(test_x)}  |  classes: {len(set(train_y))}")

    params, cv = tune(train_x, train_y, groups)
    print("Chosen by cross-validation:", params)
    cv_scores = cross_validated(train_x, train_y, groups, params, cv)
    oof = out_of_fold(train_x, train_y, groups, params, cv)
    fusion, fusion_f1 = tune_fusion(train_x, train_y, oof)
    print(f"Fusion thresholds chosen on out-of-fold training predictions: {fusion} (macro F1 {fusion_f1:.3f})")

    models = IncidentModels().train(params=params, save=True, fusion=fusion)

    from ai.incident_analyzer import IncidentAnalyzer
    rules_only = IncidentAnalyzer(use_ml=False)
    hybrid = IncidentAnalyzer(use_ml=True, ml_models=models)

    def as_label(problem):
        return OTHER if problem == "unknown" else problem

    predictions = {
        "rules": [as_label(rules_only.analyze(t)["problem"]) for t in test_x],
        "logistic_regression": list(models.logreg.predict(test_x)),
        "random_forest": list(models.forest.predict(test_x)),
        "hybrid": [as_label(hybrid.analyze(t)["problem"]) for t in test_x],
    }

    report = {
        "dataset": {"train_rows": len(train_x), "train_sentences": len(set(groups)), "test_rows": len(test_x),
                    "classes": list(LABELS),
                    "note": "Example descriptions written by the project team; the test set was written separately."},
        "sklearn_version": sklearn.__version__,
        "chosen_params": params,
        "fusion_thresholds": fusion,
        "fusion_macro_f1_out_of_fold": fusion_f1,
        "cross_validation_on_training_set": cv_scores,
        "test_set": {},
        "confusion_matrices": {},
        "misclassified": {},
    }
    for name, pred in predictions.items():
        report["test_set"][name] = metrics(test_y, pred)
        report["confusion_matrices"][name] = confusion_matrix(test_y, pred, labels=list(LABELS)).tolist()
        report["misclassified"][name] = [{"text": t, "true": y, "predicted": p}
                                         for t, y, p in zip(test_x, test_y, pred) if y != p]
    report["per_class_logistic_regression"] = classification_report(
        test_y, predictions["logistic_regression"], labels=list(LABELS), output_dict=True, zero_division=0)
    report["decision_sources_on_test_set"] = {}
    for t in test_x:
        src = hybrid.analyze(t)["decision_source"]
        report["decision_sources_on_test_set"][src] = report["decision_sources_on_test_set"].get(src, 0) + 1

    EVAL_DIR.mkdir(exist_ok=True)
    images = {}
    for name, title in (("logistic_regression", "TF-IDF + Logistic Regression (test set)"),
                        ("random_forest", "TF-IDF + Random Forest (test set)"),
                        ("hybrid", "Hybrid: rules + ML (test set)")):
        images[name] = save_confusion(test_y, predictions[name], title, EVAL_DIR / f"confusion_matrix_{name}.png")
    report["confusion_matrix_images"] = images
    report["seconds"] = round(time.time() - started, 1)
    REPORT_FILE.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print("\nCross-validation on the training set (5 grouped folds):")
    for name, s in cv_scores.items():
        print(f"  {name:20s} accuracy {s['accuracy_mean']:.3f} ± {s['accuracy_std']:.3f}   "
              f"macro F1 {s['f1_macro_mean']:.3f} ± {s['f1_macro_std']:.3f}")
    print(f"\nHeld-out test set ({len(test_x)} sentences):")
    for name, s in report["test_set"].items():
        print(f"  {name:20s} accuracy {s['accuracy']:.3f}   precision {s['precision_macro']:.3f}   "
              f"recall {s['recall_macro']:.3f}   macro F1 {s['f1_macro']:.3f}")
    print("\nHow the hybrid decided on the test set:", report["decision_sources_on_test_set"])
    print(f"\nModels saved in {models.model_dir}; report: {REPORT_FILE}")


if __name__ == "__main__":
    main()
