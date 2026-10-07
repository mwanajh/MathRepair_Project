"""Retrain the typed verifier on reviewed natural model traces.

The current TF-IDF logistic regression remains the baseline. A second model
projects those same features with truncated SVD. Both are scored on held-out
natural traces. The synthetic verifier is evaluated on the same splits and is
not retrained on them.

Repair labels come from the reviewed trace validity. A correct sampled answer
is not treated as VALID_NO_REPAIR, and the reference answer is not a feature.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import joblib
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.decomposition import TruncatedSVD
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import f1_score
from sklearn.pipeline import Pipeline

from error_taxonomy import ERROR_TYPE_CODES, VALID_NO_REPAIR
from learned_verifier import (
    _text_features,
    load_examples,
    serialize_node,
    stratified_example_split,
    train_verifier,
)
from natural_error_dataset import (
    DEFAULT_REPORT,
    DEFAULT_REVIEWS,
    DEFAULT_TRACES,
    LABEL_REVIEWED,
    apply_rescored_answers,
    apply_reviews,
    build_annotation_queue,
    dataset_statistics,
    load_checkpoint,
    load_checkpoint_supplements,
    load_supplemental_equation_traces,
)


PROJECT_DIR = Path(__file__).resolve().parent
SYNTHETIC_DATASET = PROJECT_DIR / "typed_verifier_pilot.json"
DEFAULT_OUTPUT = PROJECT_DIR / "natural_verifier_report.json"
COMPARISON_SEEDS = (42, 7, 11, 19, 23)
PRIMARY_SEED = COMPARISON_SEEDS[0]
TYPE_LABELS = (VALID_NO_REPAIR, *ERROR_TYPE_CODES)
METRIC_KEYS = (
    "repair_trigger_precision",
    "repair_trigger_recall",
    "false_positive_repair_rate",
    "error_location_accuracy",
    "error_location_f1",
    "error_type_macro_f1",
)
MODEL_PATHS = {
    "tfidf_logistic_regression": PROJECT_DIR / "natural_verifier_tfidf.joblib",
    "tfidf_svd_logistic_regression": PROJECT_DIR / "natural_verifier_tfidf_svd.joblib",
}


class CappedSVD(BaseEstimator, TransformerMixin):
    """Project TF-IDF features, shrinking the rank when the training matrix is small."""

    def __init__(self, n_components: int = 8, seed: int = 42):
        self.n_components = n_components
        self.seed = seed

    def fit(self, features, labels=None):
        n_samples, n_features = features.shape
        components = min(self.n_components, n_samples - 1, n_features - 1)
        self.n_components_ = components
        if components < 2:
            self.svd_ = None
            return self
        self.svd_ = TruncatedSVD(
            n_components=components,
            algorithm="randomized",
            random_state=self.seed,
        )
        self.svd_.fit(features)
        return self

    def transform(self, features):
        if self.svd_ is None:
            return features.toarray() if hasattr(features, "toarray") else features
        return self.svd_.transform(features)


def _pipeline(seed: int, representation: str, class_weight: str | None) -> Pipeline:
    steps: list[tuple[str, object]] = [("features", _text_features())]
    if representation == "tfidf_svd":
        steps.append(("projection", CappedSVD(n_components=8, seed=seed)))
    elif representation != "tfidf":
        raise ValueError(f"Unknown representation: {representation}")
    steps.append(
        (
            "classifier",
            LogisticRegression(
                class_weight=class_weight,
                max_iter=4000,
                random_state=seed,
            ),
        )
    )
    return Pipeline(steps)


def _inference_trace(trace: list[dict[str, object]]) -> list[dict[str, object]]:
    """Keep only fields the verifier can see at prediction time."""
    cleaned = []
    for node in trace:
        cleaned.append(
            {
                "node_id": str(node["node_id"]),
                "state": str(node.get("state", "")),
                "depends_on": [str(item) for item in node.get("depends_on", [])],
                "subgoal": str(node.get("subgoal", "")),
                "assumptions": [str(item) for item in node.get("assumptions", [])],
            }
        )
    return cleaned


def load_reviewed_examples(
    traces: Path = DEFAULT_TRACES,
    report: Path = DEFAULT_REPORT,
    reviews: Path = DEFAULT_REVIEWS,
) -> tuple[list[dict[str, object]], dict[str, object], list[str]]:
    """Load reviewed natural traces without sampling flags or reference answers."""
    records = load_checkpoint(traces)
    if report.exists():
        records = apply_rescored_answers(
            records, json.loads(report.read_text(encoding="utf-8"))
        )
    records.update(load_supplemental_equation_traces())
    records.update(load_checkpoint_supplements())
    queue = build_annotation_queue(records)
    if reviews.exists():
        queue = apply_reviews(queue, json.loads(reviews.read_text(encoding="utf-8")))
    statistics = dataset_statistics(records, queue)
    if not statistics["trainable"]:
        raise ValueError(
            "Natural verifier training requires three reviewed examples of every class."
        )
    excluded = [
        str(item["benchmark_id"])
        for item in queue
        if item["label_status"] != LABEL_REVIEWED
    ]
    examples = []
    for item in queue:
        if item["label_status"] != LABEL_REVIEWED:
            continue
        examples.append(
            {
                "example_id": str(item["example_id"]),
                "problem": str(item["problem"]),
                "trace": _inference_trace(list(item["trace"])),
                "error_location": item["error_location"],
                "error_type": str(item["error_type"]),
            }
        )
    return examples, statistics, excluded


@dataclass
class NaturalErrorVerifier:
    """First-error locator trained on reviewed natural traces."""

    location_model: Pipeline
    type_model: Pipeline
    location_threshold: float
    seed: int
    representation: str

    def predict(self, problem: str, trace: list[dict[str, object]]) -> dict[str, object]:
        if not trace:
            raise ValueError("Cannot verify an empty reasoning trace.")
        features = [
            serialize_node(problem, trace, index, include_graph=True)
            for index in range(len(trace))
        ]
        classes = list(self.location_model.named_steps["classifier"].classes_)
        positive = classes.index(1)
        probabilities = self.location_model.predict_proba(features)[:, positive]
        best_index = int(probabilities.argmax())
        confidence = float(probabilities[best_index])
        if confidence < self.location_threshold:
            return {
                "error_location": None,
                "error_type": "",
                "location_confidence": confidence,
            }
        return {
            "error_location": str(trace[best_index].get("node_id", f"n{best_index + 1}")),
            "error_type": str(self.type_model.predict([features[best_index]])[0]),
            "location_confidence": confidence,
        }


def _location_rows(
    examples: list[dict[str, object]],
) -> tuple[list[str], list[int]]:
    texts: list[str] = []
    labels: list[int] = []
    for example in examples:
        trace = list(example["trace"])
        for index, node in enumerate(trace):
            texts.append(serialize_node(str(example["problem"]), trace, index))
            labels.append(int(node["node_id"] == example["error_location"]))
    return texts, labels


def _type_rows(examples: list[dict[str, object]]) -> tuple[list[str], list[str]]:
    texts: list[str] = []
    labels: list[str] = []
    for example in examples:
        if example["error_type"] == VALID_NO_REPAIR:
            continue
        trace = list(example["trace"])
        index = next(
            i
            for i, node in enumerate(trace)
            if node["node_id"] == example["error_location"]
        )
        texts.append(serialize_node(str(example["problem"]), trace, index))
        labels.append(str(example["error_type"]))
    return texts, labels


def fit_natural_verifier(
    train: list[dict[str, object]],
    dev: list[dict[str, object]],
    seed: int,
    representation: str,
) -> NaturalErrorVerifier:
    """Fit one representation and choose its repair threshold on development traces."""
    location_texts, location_labels = _location_rows(train)
    type_texts, type_labels = _type_rows(train)
    if set(location_labels) != {0, 1}:
        raise ValueError("Location training needs both valid nodes and an error node.")
    if set(type_labels) != set(ERROR_TYPE_CODES):
        raise ValueError("Type training split is missing an error class.")
    verifier = NaturalErrorVerifier(
        location_model=_pipeline(seed, representation, "balanced").fit(
            location_texts, location_labels
        ),
        type_model=_pipeline(seed, representation, None).fit(type_texts, type_labels),
        location_threshold=0.5,
        seed=seed,
        representation=representation,
    )
    verifier.location_threshold = select_location_threshold(verifier, dev)
    return verifier


def _predicted_type(prediction: dict[str, object]) -> str:
    if prediction["error_location"] is None:
        return VALID_NO_REPAIR
    return str(prediction.get("error_type") or "")


def score_predictions(
    examples: list[dict[str, object]],
    predictions: list[dict[str, object]],
) -> dict[str, object]:
    """Score repair triggering, first-error location, and error type."""
    if len(examples) != len(predictions):
        raise ValueError("Predictions do not match examples.")
    expected_types: list[str] = []
    predicted_types: list[str] = []
    trigger_tp = trigger_fp = trigger_fn = trigger_tn = 0
    location_tp = location_fp = location_fn = 0
    invalid_hits = invalid_count = valid_count = 0
    for example, prediction in zip(examples, predictions):
        expected_type = str(example["error_type"])
        expected_location = example["error_location"]
        predicted_location = prediction["error_location"]
        triggered = predicted_location is not None
        expected_types.append(expected_type)
        predicted_types.append(_predicted_type(prediction))
        invalid = expected_type != VALID_NO_REPAIR
        if invalid:
            invalid_count += 1
            exact = predicted_location == expected_location
            if exact:
                invalid_hits += 1
                location_tp += 1
            else:
                location_fn += 1
                if triggered:
                    location_fp += 1
            if triggered:
                trigger_tp += 1
            else:
                trigger_fn += 1
        else:
            valid_count += 1
            if triggered:
                trigger_fp += 1
                location_fp += 1
            else:
                trigger_tn += 1

    def ratio(numerator: int, denominator: int) -> float | None:
        if denominator == 0:
            return None
        return numerator / denominator

    location_precision = ratio(location_tp, location_tp + location_fp)
    location_recall = ratio(location_tp, location_tp + location_fn)
    if invalid_count == 0 and location_fp == 0:
        location_f1 = None
    elif location_tp == 0:
        location_f1 = 0.0
    else:
        location_f1 = (
            2 * location_precision * location_recall / (location_precision + location_recall)
        )
    return {
        "example_count": len(examples),
        "valid_count": valid_count,
        "invalid_count": invalid_count,
        "repair_trigger_true_positives": trigger_tp,
        "repair_trigger_false_positives": trigger_fp,
        "repair_trigger_false_negatives": trigger_fn,
        "repair_trigger_true_negatives": trigger_tn,
        "repair_trigger_precision": ratio(trigger_tp, trigger_tp + trigger_fp),
        "repair_trigger_recall": ratio(trigger_tp, trigger_tp + trigger_fn),
        "false_positive_repair_rate": ratio(trigger_fp, valid_count),
        "error_location_accuracy": ratio(invalid_hits, invalid_count),
        "error_location_f1": location_f1,
        "error_type_macro_f1": float(
            f1_score(
                expected_types,
                predicted_types,
                labels=list(TYPE_LABELS),
                average="macro",
                zero_division=0,
            )
        ),
    }


def predict_examples(verifier: object, examples: list[dict[str, object]]) -> list[dict[str, object]]:
    return [
        verifier.predict(str(example["problem"]), list(example["trace"]))
        for example in examples
    ]


def score_verifier(verifier: object, examples: list[dict[str, object]]) -> dict[str, object]:
    return score_predictions(examples, predict_examples(verifier, examples))


def select_location_threshold(verifier: NaturalErrorVerifier, dev: list[dict[str, object]]) -> float:
    """Prefer an exact first-error match, then fewer repairs of valid traces."""
    best_threshold = 0.95
    best_key: tuple[float, float, float] | None = None
    for value in range(5, 96, 5):
        threshold = round(value / 100, 2)
        verifier.location_threshold = threshold
        metrics = score_verifier(verifier, dev)
        f1 = metrics["error_location_f1"]
        false_positive_rate = metrics["false_positive_repair_rate"]
        key = (
            -1.0 if f1 is None else float(f1),
            0.0 if false_positive_rate is None else -float(false_positive_rate),
            threshold,
        )
        if best_key is None or key > best_key:
            best_key = key
            best_threshold = threshold
    return best_threshold


def _summarize(rows: list[dict[str, object]]) -> dict[str, dict[str, float | int | None]]:
    summary: dict[str, dict[str, float | int | None]] = {}
    for key in METRIC_KEYS:
        values = [
            float(row["test_metrics"][key])
            for row in rows
            if row["test_metrics"][key] is not None
        ]
        summary[key] = {
            "mean": sum(values) / len(values) if values else None,
            "minimum": min(values) if values else None,
            "maximum": max(values) if values else None,
            "splits": len(values),
        }
    return summary


def _split_summary(split: dict[str, list[dict[str, object]]]) -> dict[str, object]:
    return {
        name: {
            "count": len(items),
            "example_ids": [item["example_id"] for item in items],
            "error_type_counts": dict(Counter(str(item["error_type"]) for item in items)),
        }
        for name, items in split.items()
    }


def _prediction_rows(
    verifier: object, examples: list[dict[str, object]]
) -> list[dict[str, object]]:
    rows = []
    for example, prediction in zip(examples, predict_examples(verifier, examples)):
        rows.append(
            {
                "example_id": example["example_id"],
                "expected_location": example["error_location"],
                "predicted_location": prediction["error_location"],
                "expected_type": example["error_type"],
                "predicted_type": _predicted_type(prediction),
                "location_confidence": prediction["location_confidence"],
            }
        )
    return rows


def _dataset_fingerprint(examples: list[dict[str, object]]) -> str:
    payload = json.dumps(examples, sort_keys=True, ensure_ascii=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def run_comparison(
    seeds: tuple[int, ...] = COMPARISON_SEEDS,
) -> tuple[dict[str, object], dict[str, NaturalErrorVerifier]]:
    """Train both natural representations and score the synthetic baseline on the same splits."""
    examples, statistics, excluded = load_reviewed_examples()
    synthetic, _ = train_verifier(load_examples(SYNTHETIC_DATASET), seed=42)
    per_seed: dict[str, list[dict[str, object]]] = {
        "tfidf_logistic_regression": [],
        "tfidf_svd_logistic_regression": [],
        "synthetic_tfidf_baseline": [],
    }
    primary_details: dict[str, dict[str, object]] = {}
    primary_split: dict[str, object] | None = None
    saved_models: dict[str, NaturalErrorVerifier] = {}
    for seed in seeds:
        split = stratified_example_split(examples, seed)
        if seed == seeds[0]:
            primary_split = _split_summary(split)
        trained = {
            "tfidf_logistic_regression": fit_natural_verifier(
                split["train"], split["dev"], seed, "tfidf"
            ),
            "tfidf_svd_logistic_regression": fit_natural_verifier(
                split["train"], split["dev"], seed, "tfidf_svd"
            ),
        }
        if seed == seeds[0]:
            saved_models = trained
        for name, verifier in trained.items():
            per_seed[name].append(
                {
                    "seed": seed,
                    "location_threshold": verifier.location_threshold,
                    "test_metrics": score_verifier(verifier, split["test"]),
                }
            )
            if seed == seeds[0]:
                primary_details[name] = {
                    "development_metrics": score_verifier(verifier, split["dev"]),
                    "test_predictions": _prediction_rows(verifier, split["test"]),
                }
        per_seed["synthetic_tfidf_baseline"].append(
            {
                "seed": seed,
                "location_threshold": synthetic.location_threshold,
                "test_metrics": score_verifier(synthetic, split["test"]),
            }
        )
        if seed == seeds[0]:
            primary_details["synthetic_tfidf_baseline"] = {
                "test_predictions": _prediction_rows(synthetic, split["test"]),
            }
    systems = {
        "tfidf_logistic_regression": {
            "role": "retrained_tfidf_baseline",
            "representation": "word and character TF-IDF with logistic regression",
            "trained_on": "reviewed_natural_traces",
            "primary_seed_details": primary_details["tfidf_logistic_regression"],
            "splits": per_seed["tfidf_logistic_regression"],
            "repeated_split_summary": _summarize(per_seed["tfidf_logistic_regression"]),
        },
        "tfidf_svd_logistic_regression": {
            "role": "stronger_learned_representation",
            "representation": (
                "the same TF-IDF features projected by truncated SVD, then logistic regression"
            ),
            "trained_on": "reviewed_natural_traces",
            "primary_seed_details": primary_details["tfidf_svd_logistic_regression"],
            "splits": per_seed["tfidf_svd_logistic_regression"],
            "repeated_split_summary": _summarize(per_seed["tfidf_svd_logistic_regression"]),
        },
        "synthetic_tfidf_baseline": {
            "role": "current_tfidf_baseline_not_retrained",
            "representation": "word and character TF-IDF with logistic regression",
            "trained_on": "typed_verifier_pilot.json",
            "location_threshold_selected_on": "synthetic_development_split",
            "primary_seed_details": primary_details["synthetic_tfidf_baseline"],
            "splits": per_seed["synthetic_tfidf_baseline"],
            "repeated_split_summary": _summarize(per_seed["synthetic_tfidf_baseline"]),
        },
    }
    report = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "experiment": "natural_mixed_verifier_retraining",
        "primary_seed": seeds[0],
        "seeds": list(seeds),
        "dataset": {
            "source": "model_generated",
            "reviewed_count": statistics["reviewed_count"],
            "unreviewed_count": statistics["unreviewed_count"],
            "excluded_unreviewed_benchmark_ids": excluded,
            "error_type_counts": statistics["error_type_counts"],
            "trainable": statistics["trainable"],
            "example_sha256": _dataset_fingerprint(examples),
            "note": statistics["note"],
        },
        "primary_split": primary_split,
        "metric_definitions": {
            "repair_trigger_precision": (
                "Among traces where a repair is predicted, the fraction reviewed as invalid."
            ),
            "repair_trigger_recall": (
                "Among traces reviewed as invalid, the fraction where a repair is predicted."
            ),
            "false_positive_repair_rate": (
                "Among traces reviewed as valid, the fraction where a repair is predicted."
            ),
            "error_location_accuracy": (
                "Among invalid traces, the fraction whose predicted node is the reviewed first error."
            ),
            "error_location_f1": (
                "Exact-node F1. A true positive is an invalid trace with the reviewed node. "
                "Any other repair prediction is a false positive. An invalid trace without "
                "that node is a false negative."
            ),
            "error_type_macro_f1": (
                "Unweighted mean F1 over VALID_NO_REPAIR and the eight error codes. "
                "Abstention is scored as VALID_NO_REPAIR."
            ),
        },
        "systems": systems,
        "limitations": [
            "Training uses 39 reviewed model-generated traces. One unreadable trace is excluded.",
            "Each development and test split contains one example of every class, so one split is unstable.",
            "Means are across five stratified splits. They are not a large-benchmark result.",
            "The synthetic TF-IDF model is not retrained here. Its earlier perfect score was on eight synthetic examples.",
            "The stronger representation is truncated SVD over the same TF-IDF features, not a pretrained language-model encoder.",
            "Reference answers, sampling correctness, annotation notes, and recovery actions are not features.",
            "These metrics do not measure whether a later repair improves the final answer.",
        ],
    }
    return report, saved_models


def _round_numbers(value: object) -> object:
    if isinstance(value, float):
        return round(value, 6)
    if isinstance(value, dict):
        return {key: _round_numbers(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_round_numbers(item) for item in value]
    return value


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    report, models = run_comparison()
    for name, verifier in models.items():
        joblib.dump(verifier, MODEL_PATHS[name])
    args.report.write_text(
        json.dumps(_round_numbers(report), indent=2, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )
    print(f"Report: {args.report}")
    for name, system in report["systems"].items():
        print(name)
        for key in METRIC_KEYS:
            item = system["repeated_split_summary"][key]
            print(
                f"  {key}: mean={item['mean']} min={item['minimum']} max={item['maximum']}"
            )


if __name__ == "__main__":
    main()
