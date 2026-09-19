"""Evaluate MathRepair on the small beginner dataset."""

import argparse
from collections import defaultdict
import csv
from pathlib import Path

from mathrepair_demo import verify_user_step
from repair_policy import choose_repair_action


DATA_FILE = Path(__file__).with_name("evaluation_data.csv")


def percentage(correct: int, total: int) -> float:
    """Return a percentage while safely handling an empty group."""
    return 100 * correct / total if total else 0.0


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "data_file",
        nargs="?",
        type=Path,
        default=DATA_FILE,
        help="CSV dataset; defaults to evaluation_data.csv",
    )
    args = parser.parse_args()

    with args.data_file.open(encoding="utf-8", newline="") as file:
        examples = list(csv.DictReader(file))

    detection_correct = 0
    type_correct = 0
    repair_correct = 0
    action_correct = 0
    output_correct = 0
    error_examples = 0
    category_results: dict[str, list[int]] = defaultdict(lambda: [0, 0])

    print("=== MathRepair Evaluation ===")
    print(f"Dataset: {args.data_file}\n")

    for number, example in enumerate(examples, start=1):
        ok, error_type, repair, answer = verify_user_step(
            example["original"], example["proposed"]
        )
        detected_error = not ok
        expected_error = example["has_error"].lower() == "true"

        detection_match = detected_error == expected_error
        detection_correct += int(detection_match)
        predicted_action = choose_repair_action(error_type).value
        action_match = predicted_action == example["expected_action"]
        repair_match = (
            repair == example["expected_repair"]
            and answer == example["expected_answer"]
        )
        output_correct += int(repair_match)

        if expected_error:
            error_examples += 1
            type_match = error_type == example["error_type"]
            type_correct += int(type_match)
            action_correct += int(action_match)
            repair_correct += int(repair_match)
        else:
            type_match = error_type == ""

        full_match = detection_match and type_match and action_match and repair_match
        status = "PASS" if full_match else "FAIL"
        category = example["error_type"] if expected_error else "correct"
        category_results[category][0] += int(full_match)
        category_results[category][1] += 1
        print(f"Example {number}: {status}")
        if status == "FAIL":
            print(f"  Original: {example['original']}")
            print(f"  Proposed: {example['proposed']}")
            print(f"  Result: error={detected_error}, type={error_type or 'none'}")
            print(f"  Repair: {repair}; answer: {answer}")

    total = len(examples)
    print("\n--- Results ---")
    print(
        "Error detection accuracy: "
        f"{detection_correct}/{total} ({percentage(detection_correct, total):.1f}%)"
    )
    print(
        "Error-type accuracy: "
        f"{type_correct}/{error_examples} ({percentage(type_correct, error_examples):.1f}%)"
    )
    print(
        "Repair-action accuracy: "
        f"{action_correct}/{error_examples} "
        f"({percentage(action_correct, error_examples):.1f}%)"
    )
    print(
        "Solution-output accuracy: "
        f"{output_correct}/{total} ({percentage(output_correct, total):.1f}%)"
    )
    print(
        "Repair success rate: "
        f"{repair_correct}/{error_examples} ({percentage(repair_correct, error_examples):.1f}%)"
    )
    print("\n--- Full pass by category ---")
    for category in sorted(category_results):
        correct, category_total = category_results[category]
        print(
            f"{category}: {correct}/{category_total} "
            f"({percentage(correct, category_total):.1f}%)"
        )


if __name__ == "__main__":
    main()
