"""Measure the three requested ablations at the typed-verifier stage."""

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path

from learned_verifier import (
    DEFAULT_DATASET,
    LearnedTypedVerifier,
    current_rule_baseline,
    load_examples,
    train_verifier,
)


DEFAULT_OUTPUT = Path(__file__).with_name("verifier_ablation_report.json")


def predict_variant(
    variant: str,
    verifier: LearnedTypedVerifier,
    example: dict[str, object],
) -> dict[str, object]:
    """Predict with one explicitly disabled verifier component."""
    learned = verifier.predict(
        str(example["problem"]), list(example["corrupted_trace"])
    )
    if variant == "no_symbolic_tool":
        return learned
    if variant == "no_typed_error":
        return {**learned, "error_type": ""}
    rule = current_rule_baseline(example)
    if rule["error_location"] is not None:
        return {
            **rule,
            "location_confidence": 1.0,
            "prediction_source": "current_structural_symbolic_heuristics",
        }
    return {**learned, "prediction_source": "learned_verifier"}


def variant_metrics(
    variant: str,
    verifier: LearnedTypedVerifier,
    examples: list[dict[str, object]],
) -> dict[str, object]:
    predictions = [predict_variant(variant, verifier, example) for example in examples]
    location_correct = sum(
        prediction["error_location"] == example["error_location"]
        for prediction, example in zip(predictions, examples)
    )
    type_enabled = variant != "no_typed_error"
    type_correct = sum(
        prediction["error_type"] == example["error_type"]
        for prediction, example in zip(predictions, examples)
    )
    end_to_end = sum(
        prediction["error_location"] == example["error_location"]
        and prediction["error_type"] == example["error_type"]
        for prediction, example in zip(predictions, examples)
    )
    return {
        "example_count": len(examples),
        "error_location_accuracy": location_correct / len(examples),
        "error_type_accuracy": type_correct / len(examples) if type_enabled else None,
        "end_to_end_accuracy": end_to_end / len(examples) if type_enabled else None,
        "typed_error_available": type_enabled,
    }


def run_ablation(
    examples: list[dict[str, object]], seed: int = 42
) -> dict[str, object]:
    """Train matched full/no-graph models and evaluate the held-out traces."""
    full_verifier, split = train_verifier(examples, seed, include_graph=True)
    no_graph_verifier, no_graph_split = train_verifier(
        examples, seed, include_graph=False
    )
    if [item["example_id"] for item in split["test"]] != [
        item["example_id"] for item in no_graph_split["test"]
    ]:
        raise ValueError("Ablation variants do not share the same test split.")
    test = split["test"]
    variants = [
        {
            "variant_id": "full_mathrepair",
            "graph": True,
            "typed_error": True,
            "symbolic_tool_support": True,
            "metrics": variant_metrics("full_mathrepair", full_verifier, test),
        },
        {
            "variant_id": "no_graph",
            "graph": False,
            "typed_error": True,
            "symbolic_tool_support": True,
            "metrics": variant_metrics("no_graph", no_graph_verifier, test),
        },
        {
            "variant_id": "no_typed_error",
            "graph": True,
            "typed_error": False,
            "symbolic_tool_support": True,
            "metrics": variant_metrics("no_typed_error", full_verifier, test),
        },
        {
            "variant_id": "no_symbolic_tool",
            "graph": True,
            "typed_error": True,
            "symbolic_tool_support": False,
            "metrics": variant_metrics("no_symbolic_tool", full_verifier, test),
        },
    ]
    full_metrics = variants[0]["metrics"]
    for variant in variants:
        metrics = variant["metrics"]
        metrics["delta_location_accuracy_pp"] = 100 * (
            float(metrics["error_location_accuracy"])
            - float(full_metrics["error_location_accuracy"])
        )
        metrics["delta_end_to_end_accuracy_pp"] = (
            None
            if metrics["end_to_end_accuracy"] is None
            else 100
            * (
                float(metrics["end_to_end_accuracy"])
                - float(full_metrics["end_to_end_accuracy"])
            )
        )
    return {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "experiment": "typed_verifier_component_ablation",
        "evaluation_scope": "verifier_stage_only",
        "seed": seed,
        "test_example_count": len(test),
        "test_example_ids": [item["example_id"] for item in test],
        "variants": variants,
        "interpretation": (
            "These ablations measure held-out error localization and typing only. "
            "They do not establish final-answer or end-to-end repair effects."
        ),
        "limitation": (
            "The controlled test has eight synthetic examples, one per frozen "
            "error class; equal scores can reflect template simplicity."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    try:
        report = run_ablation(load_examples(args.dataset), args.seed)
        args.output.write_text(
            json.dumps(report, indent=2, ensure_ascii=True) + "\n", encoding="utf-8"
        )
    except (OSError, ValueError, TypeError) as error:
        parser.error(str(error))
    for variant in report["variants"]:
        metrics = variant["metrics"]
        print(
            f"{variant['variant_id']}: location="
            f"{metrics['error_location_accuracy']:.3f}, "
            f"end_to_end={metrics['end_to_end_accuracy']}"
        )
    print(f"Report: {args.output}")


if __name__ == "__main__":
    main()
