"""Generate reproducible controlled-corruption data for MathRepair."""

import argparse
import csv
from pathlib import Path
import random


DEFAULT_OUTPUT = Path(__file__).with_name("generated_evaluation_data.csv")
FIELDNAMES = [
    "original",
    "proposed",
    "has_error",
    "error_type",
    "expected_repair",
    "expected_answer",
    "expected_action",
]


def make_example(
    original: str,
    proposed: str,
    has_error: bool,
    error_type: str,
    repair: str,
    answer: str,
    action: str,
) -> dict[str, str]:
    """Create one CSV-ready labeled example."""
    return {
        "original": original,
        "proposed": proposed,
        "has_error": str(has_error).lower(),
        "error_type": error_type,
        "expected_repair": repair,
        "expected_answer": answer,
        "expected_action": action,
    }


def generate_examples(count_per_type: int, seed: int) -> list[dict[str, str]]:
    """Generate balanced synthetic examples with known corruptions."""
    if count_per_type < 1:
        raise ValueError("count-per-type must be at least 1.")

    random_generator = random.Random(seed)
    examples: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()

    def add_unique(example: dict[str, str]) -> bool:
        key = (example["original"], example["proposed"])
        if key in seen:
            return False
        seen.add(key)
        examples.append(example)
        return True

    added = 0
    while added < count_per_type:
        coefficient = random_generator.randint(2, 9)
        constant = random_generator.randint(1, 12)
        solution = random_generator.randint(1, 15)
        right = coefficient * (solution + constant)
        example = make_example(
            f"{coefficient}(x + {constant}) = {right}",
            f"{coefficient}x + {constant} = {right}",
            True,
            "algebraic_transformation_error",
            f"{coefficient}x + {coefficient * constant} = {right}",
            f"x = {solution}",
            "REFORMALIZE",
        )
        added += int(add_unique(example))

    added = 0
    while added < count_per_type:
        moved_value = random_generator.randint(2, 15)
        right = random_generator.randint(1, 15)
        example = make_example(
            f"x - {moved_value} = {right}",
            f"x = {right - moved_value}",
            True,
            "sign_error",
            f"x = {right + moved_value}",
            f"x = {right + moved_value}",
            "BACKTRACK",
        )
        added += int(add_unique(example))

    added = 0
    while added < count_per_type:
        first = random_generator.randint(1, 50)
        second = random_generator.randint(1, 50)
        correct_total = first + second
        wrong_total = correct_total + random_generator.choice([-2, -1, 1, 2])
        original = f"{first} + {second} = {correct_total}"
        example = make_example(
            original,
            f"{first} + {second} = {wrong_total}",
            True,
            "arithmetic_error",
            original,
            "true",
            "TOOL_EXECUTE",
        )
        added += int(add_unique(example))

    added = 0
    while added < count_per_type:
        coefficient = random_generator.randint(2, 9)
        constant = random_generator.randint(1, 12)
        solution = random_generator.randint(1, 15)
        right = coefficient * solution + constant
        original = f"{coefficient}x + {constant} = {right}"
        example = make_example(
            original,
            f"x = {solution}",
            False,
            "",
            original,
            f"x = {solution}",
            "CONTINUE",
        )
        added += int(add_unique(example))

    random_generator.shuffle(examples)
    return examples


def write_dataset(path: Path, examples: list[dict[str, str]]) -> None:
    """Write generated examples using the evaluator's CSV schema."""
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(examples)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--count-per-type", type=int, default=20)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    try:
        examples = generate_examples(args.count_per_type, args.seed)
        write_dataset(args.output, examples)
    except (OSError, ValueError) as error:
        parser.error(str(error))

    print(f"Generated {len(examples)} examples: {args.output}")
    print(f"Seed: {args.seed}; examples per type: {args.count_per_type}")


if __name__ == "__main__":
    main()
