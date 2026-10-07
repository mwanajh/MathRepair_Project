"""Train and evaluate the first learned typed verifier.

The pilot deliberately uses a small, inspectable TF-IDF/logistic-regression
baseline.  It predicts the first erroneous node and then predicts one of the
eight frozen error types without reading the clean trace or repair target.
"""

import argparse
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import random
from typing import Iterable

import joblib
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, confusion_matrix, f1_score
from sklearn.pipeline import FeatureUnion, Pipeline

from error_taxonomy import DEPENDENCY_ERROR, ERROR_TYPE_CODES
from mathrepair_demo import verify_reasoning_step


DEFAULT_DATASET = Path(__file__).with_name("typed_verifier_pilot.json")
DEFAULT_MODEL = Path(__file__).with_name("learned_verifier_model.joblib")
DEFAULT_REPORT = Path(__file__).with_name("learned_verifier_report.json")


def _text_features() -> FeatureUnion:
    return FeatureUnion(
        [
            (
                "word",
                TfidfVectorizer(
                    lowercase=True,
                    ngram_range=(1, 2),
                    min_df=1,
                    sublinear_tf=True,
                ),
            ),
            (
                "char",
                TfidfVectorizer(
                    analyzer="char_wb",
                    ngram_range=(2, 5),
                    min_df=1,
                    sublinear_tf=True,
                ),
            ),
        ]
    )


def _classifier(seed: int, class_weight: str | None = None) -> Pipeline:
    return Pipeline(
        [
            ("features", _text_features()),
            (
                "classifier",
                LogisticRegression(
                    class_weight=class_weight,
                    max_iter=4000,
                    random_state=seed,
                ),
            ),
        ]
    )


def load_examples(path: Path) -> list[dict[str, object]]:
    """Load and validate controlled verifier examples."""
    decoded = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(decoded, list) or not decoded:
        raise ValueError("Verifier dataset must be a non-empty JSON array.")
    required = {"example_id", "problem", "corrupted_trace", "error_location", "error_type"}
    for index, example in enumerate(decoded, start=1):
        if not isinstance(example, dict) or not required.issubset(example):
            raise ValueError(f"Verifier example {index} is incomplete.")
        if example["error_type"] not in ERROR_TYPE_CODES:
            raise ValueError(f"Verifier example {index} has an unknown error type.")
    return decoded


def stratified_example_split(
    examples: list[dict[str, object]], seed: int
) -> dict[str, list[dict[str, object]]]:
    """Split whole traces, preserving every error class in each partition."""
    grouped: dict[str, list[dict[str, object]]] = {}
    for example in examples:
        grouped.setdefault(str(example["error_type"]), []).append(example)
    split = {"train": [], "dev": [], "test": []}
    rng = random.Random(seed)
    for error_type in sorted(grouped):
        group = sorted(grouped[error_type], key=lambda item: str(item["example_id"]))
        if len(group) < 3:
            raise ValueError(
                f"Error type {error_type} needs at least three examples for train/dev/test."
            )
        rng.shuffle(group)
        split["test"].append(group[0])
        split["dev"].append(group[1])
        split["train"].extend(group[2:])
    for name in split:
        split[name].sort(key=lambda item: str(item["example_id"]))
    return split


def serialize_node(
    problem: str,
    trace: list[dict[str, object]],
    node_index: int,
    *,
    include_graph: bool = True,
) -> str:
    """Serialize only inference-time fields for one candidate node."""
    node = trace[node_index]
    parts = [
        f"problem: {problem}",
        f"position: {node_index + 1} of {len(trace)}",
        f"state: {node.get('state', '')}",
    ]
    if node_index:
        parts.append(f"previous_state: {trace[node_index - 1].get('state', '')}")
    if include_graph:
        parts.extend(
            [
                f"node_id: {node.get('node_id', '')}",
                f"depends_on: {' '.join(node.get('depends_on', []))}",
                f"subgoal: {node.get('subgoal', '')}",
                f"assumptions: {' '.join(node.get('assumptions', []))}",
            ]
        )
    return "\n".join(parts)


def _node_rows(
    examples: Iterable[dict[str, object]], *, include_graph: bool = True
) -> tuple[list[str], list[int]]:
    texts: list[str] = []
    labels: list[int] = []
    for example in examples:
        trace = list(example["corrupted_trace"])
        for index, node in enumerate(trace):
            texts.append(
                serialize_node(str(example["problem"]), trace, index, include_graph=include_graph)
            )
            labels.append(int(node["node_id"] == example["error_location"]))
        # Add the paired clean trace as explicit hard negatives. The original
        # training set already contained valid nodes around each corruption,
        # but clean traces teach the locator that an entirely valid solution
        # should produce no repair target when the baseline answer is correct.
        clean_trace = example.get("correct_trace")
        if isinstance(clean_trace, list):
            for index, node in enumerate(clean_trace):
                texts.append(
                    serialize_node(
                        str(example["problem"]),
                        clean_trace,
                        index,
                        include_graph=include_graph,
                    )
                )
                labels.append(0)
    return texts, labels


def _type_rows(
    examples: Iterable[dict[str, object]], *, include_graph: bool = True
) -> tuple[list[str], list[str]]:
    texts: list[str] = []
    labels: list[str] = []
    for example in examples:
        trace = list(example["corrupted_trace"])
        index = next(
            i for i, node in enumerate(trace) if node["node_id"] == example["error_location"]
        )
        texts.append(
            serialize_node(str(example["problem"]), trace, index, include_graph=include_graph)
        )
        labels.append(str(example["error_type"]))
    return texts, labels


def _trace_rows(
    examples: Iterable[dict[str, object]], *, include_graph: bool = True
) -> tuple[list[str], list[int]]:
    texts: list[str] = []
    labels: list[int] = []
    for example in examples:
        for key, label in (("correct_trace", 1), ("corrupted_trace", 0)):
            trace = example.get(key)
            if not isinstance(trace, list):
                continue
            features = [
                serialize_node(str(example["problem"]), trace, index, include_graph=include_graph)
                for index in range(len(trace))
            ]
            texts.append("\n---\n".join(features))
            labels.append(label)
    return texts, labels


@dataclass
class LearnedTypedVerifier:
    """Two-stage first-error location and type predictor."""

    location_model: Pipeline
    type_model: Pipeline
    location_threshold: float
    seed: int
    include_graph: bool = True

    def predict(
        self, problem: str, trace: list[dict[str, object]]
    ) -> dict[str, object]:
        if not trace:
            raise ValueError("Cannot verify an empty reasoning trace.")
        features = [
            serialize_node(problem, trace, index, include_graph=self.include_graph)
            for index in range(len(trace))
        ]
        probabilities = self.location_model.predict_proba(features)[:, 1]
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


def _location_accuracy(
    verifier: LearnedTypedVerifier, examples: list[dict[str, object]]
) -> float:
    correct = sum(
        verifier.predict(str(example["problem"]), list(example["corrupted_trace"]))[
            "error_location"
        ]
        == str(example["error_location"])
        for example in examples
    )
    return correct / len(examples)


def select_location_threshold(
    verifier: LearnedTypedVerifier, dev: list[dict[str, object]]
) -> float:
    """Choose a threshold using corrupted traces and paired clean negatives."""
    candidates = [round(value / 100, 2) for value in range(0, 91, 5)]
    scores = []
    clean_examples = [
        {**example, "corrupted_trace": example["correct_trace"]}
        for example in dev
        if isinstance(example.get("correct_trace"), list)
    ]
    for threshold in candidates:
        verifier.location_threshold = threshold
        corrupted_accuracy = _location_accuracy(verifier, dev)
        clean_abstention = (
            sum(
                verifier.predict(str(example["problem"]), list(example["corrupted_trace"]))[
                    "error_location"
                ]
                is None
                for example in clean_examples
            )
            / len(clean_examples)
            if clean_examples
            else 0.0
        )
        # Detection remains the primary objective; clean-trace abstention is a
        # secondary calibration signal rather than a reason to suppress known
        # corruption on the held-out error classes.
        scores.append((0.9 * corrupted_accuracy + 0.1 * clean_abstention, threshold))
    return max(scores)[1]


def current_rule_baseline(example: dict[str, object]) -> dict[str, str | None]:
    """Run only already-implemented structural and symbolic heuristics."""
    problem = str(example["problem"])
    trace = list(example["corrupted_trace"])
    seen: set[str] = set()
    for node in trace:
        node_id = str(node.get("node_id", ""))
        parents = [str(value) for value in node.get("depends_on", [])]
        if any(parent not in seen for parent in parents):
            return {"error_location": node_id, "error_type": DEPENDENCY_ERROR}
        seen.add(node_id)
        try:
            ok, error_type, _, _ = verify_reasoning_step(problem, str(node.get("state", "")))
        except Exception:
            continue
        if not ok:
            return {"error_location": node_id, "error_type": error_type}
    return {"error_location": None, "error_type": ""}


def evaluate(
    verifier: LearnedTypedVerifier, examples: list[dict[str, object]]
) -> dict[str, object]:
    expected_locations = [str(example["error_location"]) for example in examples]
    expected_types = [str(example["error_type"]) for example in examples]
    predictions = [
        verifier.predict(str(example["problem"]), list(example["corrupted_trace"]))
        for example in examples
    ]
    predicted_locations = [item["error_location"] for item in predictions]
    predicted_types = [str(item["error_type"]) for item in predictions]
    end_to_end = [
        predicted_locations[index] == expected_locations[index]
        and predicted_types[index] == expected_types[index]
        for index in range(len(examples))
    ]
    matrix = confusion_matrix(
        expected_types, predicted_types, labels=list(ERROR_TYPE_CODES)
    )
    return {
        "example_count": len(examples),
        "error_location_accuracy": accuracy_score(expected_locations, predicted_locations),
        "error_type_accuracy": accuracy_score(expected_types, predicted_types),
        "error_type_macro_f1": f1_score(
            expected_types,
            predicted_types,
            labels=list(ERROR_TYPE_CODES),
            average="macro",
            zero_division=0,
        ),
        "end_to_end_accuracy": sum(end_to_end) / len(end_to_end),
        "confusion_matrix": {
            "labels": list(ERROR_TYPE_CODES),
            "values": matrix.tolist(),
        },
        "predictions": [
            {
                "example_id": example["example_id"],
                "expected_location": expected_locations[index],
                "predicted_location": predicted_locations[index],
                "expected_type": expected_types[index],
                "predicted_type": predicted_types[index],
                "location_confidence": predictions[index]["location_confidence"],
            }
            for index, example in enumerate(examples)
        ],
    }


def evaluate_rule_baseline(examples: list[dict[str, object]]) -> dict[str, object]:
    predictions = [current_rule_baseline(example) for example in examples]
    covered = [item for item in predictions if item["error_location"] is not None]
    location_correct = sum(
        prediction["error_location"] == example["error_location"]
        for example, prediction in zip(examples, predictions)
    )
    type_correct = sum(
        prediction["error_type"] == example["error_type"]
        for example, prediction in zip(examples, predictions)
    )
    return {
        "name": "current_structural_symbolic_heuristics",
        "example_count": len(examples),
        "coverage": len(covered) / len(examples),
        "error_location_accuracy_with_abstentions_wrong": location_correct / len(examples),
        "error_type_accuracy_with_abstentions_wrong": type_correct / len(examples),
        "prediction_counts": dict(Counter(str(item["error_type"] or "abstain") for item in predictions)),
    }


def train_verifier(
    examples: list[dict[str, object]], seed: int = 42, *, include_graph: bool = True
) -> tuple[LearnedTypedVerifier, dict[str, list[dict[str, object]]]]:
    split = stratified_example_split(examples, seed)
    location_texts, location_labels = _node_rows(split["train"], include_graph=include_graph)
    type_texts, type_labels = _type_rows(split["train"], include_graph=include_graph)
    verifier = LearnedTypedVerifier(
        location_model=_classifier(seed, class_weight="balanced").fit(
            location_texts, location_labels
        ),
        type_model=_classifier(seed).fit(type_texts, type_labels),
        location_threshold=0.5,
        seed=seed,
        include_graph=include_graph,
    )
    verifier.location_threshold = select_location_threshold(verifier, split["dev"])
    return verifier, split


def build_report(
    verifier: LearnedTypedVerifier,
    split: dict[str, list[dict[str, object]]],
    dataset_path: Path,
) -> dict[str, object]:
    test_metrics = evaluate(verifier, split["test"])
    return {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "experiment": "learned_typed_verifier_pilot",
        "model_family": "tfidf_logistic_regression",
        "seed": verifier.seed,
        "location_threshold_selected_on_dev": verifier.location_threshold,
        "dataset": {
            "path": dataset_path.name,
            "sha256": hashlib.sha256(dataset_path.read_bytes()).hexdigest(),
            "source": "controlled_synthetic",
            "example_count": sum(len(items) for items in split.values()),
        },
        "split": {
            name: {
                "count": len(items),
                "example_ids": [item["example_id"] for item in items],
                "error_type_counts": dict(Counter(str(item["error_type"]) for item in items)),
            }
            for name, items in split.items()
        },
        "dev_metrics": evaluate(verifier, split["dev"]),
        "test_metrics": test_metrics,
        "test_rule_baseline": evaluate_rule_baseline(split["test"]),
        "limitations": [
            "The dataset has only 48 controlled synthetic examples.",
            "The eight-example test split gives one example per error type.",
            "Results are a pipeline pilot, not evidence of broad mathematical generalization.",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--model-output", type=Path, default=DEFAULT_MODEL)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    try:
        examples = load_examples(args.dataset)
        verifier, split = train_verifier(examples, args.seed)
        report = build_report(verifier, split, args.dataset)
        joblib.dump(verifier, args.model_output)
        args.report.write_text(
            json.dumps(report, indent=2, ensure_ascii=True) + "\n", encoding="utf-8"
        )
    except (OSError, ValueError, TypeError) as error:
        parser.error(str(error))
    metrics = report["test_metrics"]
    print(f"Test location accuracy: {metrics['error_location_accuracy']:.3f}")
    print(f"Test error-type accuracy: {metrics['error_type_accuracy']:.3f}")
    print(f"Model: {args.model_output}")
    print(f"Report: {args.report}")


if __name__ == "__main__":
    main()
