"""Compare three recovery policies on reviewed natural traces.

A always chooses global regeneration. B always chooses local repair.
C is a TF-IDF logistic-regression router trained on the reviewed recovery
action. The comparison scores agreement with those labels. It does not
generate a repair and it does not read the reference answer.
"""

from __future__ import annotations

import argparse
import json
import random
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import joblib
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, f1_score
from sklearn.pipeline import Pipeline

from learned_verifier import _text_features, serialize_node
from natural_error_dataset import (
    DEFAULT_REPORT,
    DEFAULT_REVIEWS,
    DEFAULT_TRACES,
    LABEL_REVIEWED,
    RECOVERY_ACTIONS,
    apply_rescored_answers,
    apply_reviews,
    build_annotation_queue,
    load_checkpoint,
    load_checkpoint_supplements,
    load_supplemental_equation_traces,
)
from natural_verifier import _inference_trace


PROJECT_DIR = Path(__file__).resolve().parent
DEFAULT_OUTPUT = PROJECT_DIR / "recovery_routing_report.json"
DEFAULT_MODEL = PROJECT_DIR / "recovery_router_tfidf.joblib"
COMPARISON_SEEDS = (42, 7, 11, 19, 23)
ALWAYS_GLOBAL = "GLOBAL_REGENERATE"
ALWAYS_LOCAL = "LOCAL_REPAIR"
METRIC_KEYS = ("action_accuracy", "action_macro_f1")


def load_routing_examples() -> tuple[list[dict[str, object]], list[str], list[str]]:
    """Load reviewed traces. The recovery label stays outside the trace text."""
    records = load_checkpoint(DEFAULT_TRACES)
    if DEFAULT_REPORT.exists():
        records = apply_rescored_answers(
            records, json.loads(DEFAULT_REPORT.read_text(encoding="utf-8"))
        )
    records.update(load_supplemental_equation_traces())
    records.update(load_checkpoint_supplements())
    queue = build_annotation_queue(records)
    if DEFAULT_REVIEWS.exists():
        queue = apply_reviews(queue, json.loads(DEFAULT_REVIEWS.read_text(encoding="utf-8")))
    examples = []
    for item in queue:
        if item["label_status"] != LABEL_REVIEWED:
            continue
        action = str(item["recovery_action"])
        if action not in RECOVERY_ACTIONS:
            raise ValueError(f"Unknown recovery action: {action}")
        examples.append(
            {
                "example_id": str(item["example_id"]),
                "problem": str(item["problem"]),
                "trace": _inference_trace(list(item["trace"])),
                "recovery_action": action,
            }
        )
    counts = Counter(str(item["recovery_action"]) for item in examples)
    thin = [action for action in RECOVERY_ACTIONS if 0 < counts[action] < 3]
    if thin:
        raise ValueError(
            "Recovery routing needs three reviewed examples of every observed action: "
            + ", ".join(thin)
        )
    unobserved = [action for action in RECOVERY_ACTIONS if counts[action] == 0]
    observed = [action for action in RECOVERY_ACTIONS if counts[action] >= 3]
    if not observed:
        raise ValueError("No recovery action has three reviewed examples.")
    return examples, observed, unobserved


def trace_text(example: dict[str, object]) -> str:
    """Serialize inference-time fields for one trace."""
    trace = list(example["trace"])
    parts = [
        serialize_node(str(example["problem"]), trace, index)
        for index in range(len(trace))
    ]
    return "\n---\n".join(parts)


def stratified_action_split(
    examples: list[dict[str, object]],
    seed: int,
) -> dict[str, list[dict[str, object]]]:
    """Hold out one trace of each observed recovery action for dev and test."""
    grouped: dict[str, list[dict[str, object]]] = {}
    for example in examples:
        grouped.setdefault(str(example["recovery_action"]), []).append(example)
    split: dict[str, list[dict[str, object]]] = {"train": [], "dev": [], "test": []}
    rng = random.Random(seed)
    for action in sorted(grouped):
        group = sorted(grouped[action], key=lambda item: str(item["example_id"]))
        if len(group) < 3:
            raise ValueError(f"{action} needs at least three examples for train/dev/test.")
        rng.shuffle(group)
        split["test"].append(group[0])
        split["dev"].append(group[1])
        split["train"].extend(group[2:])
    for name in split:
        split[name].sort(key=lambda item: str(item["example_id"]))
    return split


def fit_router(train: list[dict[str, object]], seed: int) -> Pipeline:
    """Fit the learned routing policy on training traces only."""
    model = Pipeline(
        [
            ("features", _text_features()),
            (
                "classifier",
                LogisticRegression(
                    class_weight="balanced",
                    max_iter=4000,
                    random_state=seed,
                ),
            ),
        ]
    )
    model.fit(
        [trace_text(example) for example in train],
        [str(example["recovery_action"]) for example in train],
    )
    return model


def score_actions(
    expected: list[str],
    predicted: list[str],
    labels: list[str],
) -> dict[str, float]:
    """Score one policy on the actions present in this split."""
    return {
        "example_count": len(expected),
        "action_accuracy": float(accuracy_score(expected, predicted)),
        "action_macro_f1": float(
            f1_score(expected, predicted, labels=labels, average="macro", zero_division=0)
        ),
    }


def _constant_predictions(action: str, count: int) -> list[str]:
    return [action] * count


def _summarize(rows: list[dict[str, object]]) -> dict[str, dict[str, float | int | None]]:
    summary: dict[str, dict[str, float | int | None]] = {}
    for key in METRIC_KEYS:
        values = [float(row["test_metrics"][key]) for row in rows]
        summary[key] = {
            "mean": sum(values) / len(values) if values else None,
            "minimum": min(values) if values else None,
            "maximum": max(values) if values else None,
            "splits": len(values),
        }
    return summary


def _round_numbers(value: object) -> object:
    if isinstance(value, float):
        return round(value, 6)
    if isinstance(value, dict):
        return {key: _round_numbers(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_round_numbers(item) for item in value]
    return value


def run_comparison(
    seeds: tuple[int, ...] = COMPARISON_SEEDS,
) -> tuple[dict[str, object], Pipeline | None]:
    """Score the two fixed policies and the learned router on the same splits."""
    examples, observed, unobserved = load_routing_examples()
    counts = dict(Counter(str(item["recovery_action"]) for item in examples))
    per_policy: dict[str, list[dict[str, object]]] = {
        "always_global_regeneration": [],
        "always_local_repair": [],
        "learned_tfidf_routing": [],
    }
    primary_details: dict[str, dict[str, object]] = {}
    saved_model: Pipeline | None = None
    for seed in seeds:
        split = stratified_action_split(examples, seed)
        expected = [str(item["recovery_action"]) for item in split["test"]]
        router = fit_router(split["train"], seed)
        if seed == seeds[0]:
            saved_model = router
        predictions = {
            "always_global_regeneration": _constant_predictions(ALWAYS_GLOBAL, len(expected)),
            "always_local_repair": _constant_predictions(ALWAYS_LOCAL, len(expected)),
            "learned_tfidf_routing": [
                str(action) for action in router.predict([trace_text(item) for item in split["test"]])
            ],
        }
        for name, predicted in predictions.items():
            per_policy[name].append(
                {
                    "seed": seed,
                    "test_metrics": score_actions(expected, predicted, observed),
                }
            )
            if seed == seeds[0]:
                primary_details[name] = {
                    "test_predictions": [
                        {
                            "example_id": item["example_id"],
                            "expected_action": expected[index],
                            "predicted_action": predicted[index],
                        }
                        for index, item in enumerate(split["test"])
                    ]
                }
    full_expected = [str(item["recovery_action"]) for item in examples]
    descriptive = {
        "always_global_regeneration": score_actions(
            full_expected, _constant_predictions(ALWAYS_GLOBAL, len(examples)), observed
        ),
        "always_local_repair": score_actions(
            full_expected, _constant_predictions(ALWAYS_LOCAL, len(examples)), observed
        ),
    }
    report = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "experiment": "recovery_routing_comparison",
        "primary_seed": seeds[0],
        "seeds": list(seeds),
        "dataset": {
            "reviewed_count": len(examples),
            "recovery_action_counts": counts,
            "observed_recovery_actions": observed,
            "unobserved_recovery_actions": unobserved,
        },
        "policies": {
            "always_global_regeneration": {
                "role": "A_always_global_regeneration",
                "predicted_action": ALWAYS_GLOBAL,
                "full_set_agreement": descriptive["always_global_regeneration"],
                "primary_seed_details": primary_details["always_global_regeneration"],
                "splits": per_policy["always_global_regeneration"],
                "repeated_split_summary": _summarize(per_policy["always_global_regeneration"]),
            },
            "always_local_repair": {
                "role": "B_always_local_repair",
                "predicted_action": ALWAYS_LOCAL,
                "full_set_agreement": descriptive["always_local_repair"],
                "primary_seed_details": primary_details["always_local_repair"],
                "splits": per_policy["always_local_repair"],
                "repeated_split_summary": _summarize(per_policy["always_local_repair"]),
            },
            "learned_tfidf_routing": {
                "role": "C_learned_recovery_routing",
                "representation": "word and character TF-IDF with logistic regression",
                "trained_on": "reviewed_recovery_actions",
                "primary_seed_details": primary_details["learned_tfidf_routing"],
                "splits": per_policy["learned_tfidf_routing"],
                "repeated_split_summary": _summarize(per_policy["learned_tfidf_routing"]),
            },
        },
        "metric_definitions": {
            "action_accuracy": "Fraction of traces whose predicted action equals the reviewed recovery action.",
            "action_macro_f1": "Unweighted mean F1 over the observed recovery actions in the split.",
        },
        "limitations": [
            "The score is agreement with the reviewed recovery action, not a change in the final answer.",
            "No repair was generated for this comparison, and the larger benchmark remains blocked.",
            "GLOBAL_REGENERATE has no reviewed example. Agreement of zero is an empty category, not a repair-quality result.",
            "Each test split contains one example of every observed action, so one split is unstable.",
            "Reference answers, sampling correctness, annotation notes, error locations, and error types are not features.",
        ],
    }
    return report, saved_model


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--model-output", type=Path, default=DEFAULT_MODEL)
    args = parser.parse_args()
    report, model = run_comparison()
    if model is not None:
        joblib.dump(model, args.model_output)
    args.report.write_text(
        json.dumps(_round_numbers(report), indent=2, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )
    print(f"Report: {args.report}")
    for name, policy in report["policies"].items():
        summary = policy["repeated_split_summary"]
        print(name)
        for key in METRIC_KEYS:
            item = summary[key]
            print(f"  {key}: mean={item['mean']} min={item['minimum']} max={item['maximum']}")


if __name__ == "__main__":
    main()
