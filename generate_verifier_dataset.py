"""Generate controlled typed-verifier training examples."""

import argparse
from collections import Counter
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import random

from error_taxonomy import (
    ALGEBRAIC_TRANSFORMATION_ERROR,
    ARITHMETIC_ERROR,
    DEPENDENCY_ERROR,
    INCOMPLETE_SOLUTION,
    LOGICAL_INFERENCE_ERROR,
    MISSING_ASSUMPTION,
    SEMANTIC_INTERPRETATION_ERROR,
    SIGN_ERROR,
    get_error_spec,
)
from repair_policy import choose_repair_action


DEFAULT_OUTPUT = Path(__file__).with_name("typed_verifier_pilot.json")
DEFAULT_MANIFEST = Path(__file__).with_name("typed_verifier_pilot_manifest.json")


@dataclass(frozen=True)
class NodeTemplate:
    node_id: str
    state: str
    depends_on: tuple[str, ...]
    subgoal: str
    assumptions: tuple[str, ...] = ()


@dataclass(frozen=True)
class Corruption:
    error_type: str
    variant: str
    error_location: str
    corrupted_state: str
    correct_state: str
    corrupted_depends_on: tuple[str, ...] | None = None
    corrupted_assumptions: tuple[str, ...] | None = None


def node_record(node: NodeTemplate, *, state: str | None = None, depends_on: tuple[str, ...] | None = None, assumptions: tuple[str, ...] | None = None) -> dict[str, object]:
    """Serialize one trace node with the fields used by the learned verifier."""
    final_state = state if state is not None else node.state
    parents = depends_on if depends_on is not None else node.depends_on
    active_assumptions = assumptions if assumptions is not None else node.assumptions
    return {
        "node_id": node.node_id,
        "state": final_state,
        "model_generated_reasoning": final_state,
        "depends_on": list(parents),
        "subgoal": node.subgoal,
        "assumptions": list(active_assumptions),
    }


def make_example(
    problem: str,
    correct_nodes: tuple[NodeTemplate, ...],
    corruption: Corruption,
    sample_index: int,
) -> dict[str, object]:
    """Create one paired clean/corrupted graph example."""
    correct_trace = [node_record(node) for node in correct_nodes]
    corrupted_trace = [node_record(node) for node in correct_nodes]
    target_index = next(
        index
        for index, node in enumerate(correct_nodes)
        if node.node_id == corruption.error_location
    )
    target = correct_nodes[target_index]
    corrupted_trace[target_index] = node_record(
        target,
        state=corruption.corrupted_state,
        depends_on=corruption.corrupted_depends_on,
        assumptions=corruption.corrupted_assumptions,
    )
    spec = get_error_spec(corruption.error_type)
    if spec is None:
        raise ValueError(f"Unknown taxonomy code: {corruption.error_type}")
    return {
        "example_id": f"controlled-{corruption.error_type}-{sample_index:03d}",
        "source": "controlled_synthetic",
        "sample_index": sample_index,
        "problem": problem,
        "correct_trace": correct_trace,
        "corrupted_trace": corrupted_trace,
        "error_location": corruption.error_location,
        "error_type": corruption.error_type,
        "corruption_variant": corruption.variant,
        "corrupted_step": corruption.corrupted_state,
        "correct_step": corruption.correct_state,
        "preferred_repair_action": choose_repair_action(
            corruption.error_type
        ).value,
        "allowed_repair_actions": list(spec.recommended_actions),
        "label_source": "controlled_corruption",
    }


def _algebraic_examples() -> list[tuple[str, tuple[NodeTemplate, ...], Corruption]]:
    examples = []
    for coefficient, constant, answer in [
        (2, 3, 4),
        (3, 4, 5),
        (4, 2, 6),
        (5, 1, 7),
        (6, 3, 8),
        (7, 2, 9),
    ]:
        right = coefficient * (answer + constant)
        problem = f"{coefficient}(x + {constant}) = {right}"
        correct = (
            NodeTemplate("n1", problem, (), "state the problem"),
            NodeTemplate(
                "n2",
                f"{coefficient}x + {coefficient * constant} = {right}",
                ("n1",),
                "expand the product",
            ),
            NodeTemplate("n3", f"x = {answer}", ("n2",), "isolate x"),
        )
        examples.append(
            (
                problem,
                correct,
                Corruption(
                    ALGEBRAIC_TRANSFORMATION_ERROR,
                    "invalid_expansion",
                    "n2",
                    f"{coefficient}x + {constant} = {right}",
                    correct[1].state,
                ),
            )
        )
    return examples


def _sign_examples() -> list[tuple[str, tuple[NodeTemplate, ...], Corruption]]:
    examples = []
    for offset, right in [(2, 3), (4, 5), (6, 2), (7, 4), (8, 1), (9, 6)]:
        answer = right + offset
        problem = f"x - {offset} = {right}"
        correct = (
            NodeTemplate("n1", problem, (), "state the problem"),
            NodeTemplate("n2", f"x = {answer}", ("n1",), "move the constant"),
        )
        examples.append(
            (
                problem,
                correct,
                Corruption(
                    SIGN_ERROR,
                    "wrong_sign",
                    "n2",
                    f"x = {right - offset}",
                    correct[1].state,
                ),
            )
        )
    return examples


def _arithmetic_examples() -> list[tuple[str, tuple[NodeTemplate, ...], Corruption]]:
    examples = []
    for index, (left, right) in enumerate(
        [(12, 4), (15, 3), (18, 6), (21, 7), (24, 8), (27, 9)]
    ):
        correct_value = left // right
        problem = f"{left}/{right} = {correct_value}"
        correct = (
            NodeTemplate("n1", problem, (), "evaluate the arithmetic expression"),
        )
        incorrect_number = index < 3
        corrupted_state = (
            f"{left + 1}/{right} = {correct_value}"
            if incorrect_number
            else f"{left}/{right} = {correct_value + 1}"
        )
        examples.append(
            (
                problem,
                correct,
                Corruption(
                    ARITHMETIC_ERROR,
                    "incorrect_number" if incorrect_number else "arithmetic_calculation",
                    "n1",
                    corrupted_state,
                    correct[0].state,
                ),
            )
        )
    return examples


def _incomplete_examples() -> list[tuple[str, tuple[NodeTemplate, ...], Corruption]]:
    examples = []
    for coefficient, answer in [(2, 4), (3, 5), (4, 6), (5, 7), (6, 8), (7, 9)]:
        right = coefficient * answer
        problem = f"{coefficient}x = {right}"
        correct = (
            NodeTemplate("n1", problem, (), "state the problem"),
            NodeTemplate("n2", f"x = {answer}", ("n1",), "isolate x"),
        )
        examples.append(
            (
                problem,
                correct,
                Corruption(
                    INCOMPLETE_SOLUTION,
                    "missing_final_isolation",
                    "n2",
                    f"{coefficient}x = {right}",
                    correct[1].state,
                ),
            )
        )
    return examples


def _dependency_examples() -> list[tuple[str, tuple[NodeTemplate, ...], Corruption]]:
    examples = []
    for index in range(6):
        problem = f"x + {index + 1} = {index + 3}"
        correct = (
            NodeTemplate("n1", problem, (), "state the problem"),
            NodeTemplate(
                "n2", f"x + {index + 1} = {index + 3}", ("n1",), "preserve the equation"
            ),
            NodeTemplate("n3", "x = 2", ("n2",), "isolate x"),
            NodeTemplate(
                "n4", "2 = x", ("n1",), "state an equivalent answer"
            ),
        )
        examples.append(
            (
                problem,
                correct,
                Corruption(
                    DEPENDENCY_ERROR,
                    "wrong_parent_dependency",
                    "n3",
                    correct[2].state,
                    correct[2].state,
                    corrupted_depends_on=("n4",),
                ),
            )
        )
    return examples


def _assumption_examples() -> list[tuple[str, tuple[NodeTemplate, ...], Corruption]]:
    examples = []
    for index in range(6):
        problem = f"Solve x^2 = {index + 4} for x given x >= 0."
        correct = (
            NodeTemplate("n1", problem, (), "state the problem", ("x >= 0",)),
            NodeTemplate(
                "n2", f"x = sqrt({index + 4})", ("n1",), "take the principal root", ("x >= 0",)
            ),
        )
        examples.append(
            (
                problem,
                correct,
                Corruption(
                    MISSING_ASSUMPTION,
                    "dropped_assumption",
                    "n2",
                    f"x = +/-sqrt({index + 4})",
                    correct[1].state,
                    corrupted_assumptions=(),
                ),
            )
        )
    return examples


def _logical_examples() -> list[tuple[str, tuple[NodeTemplate, ...], Corruption]]:
    examples = []
    # Each 2*p value below has exactly two positive even divisors: 2 and itself.
    for divisor in [6, 10, 14, 22, 26, 34]:
        problem = f"n is a positive even divisor of {divisor}."
        correct = (
            NodeTemplate("n1", problem, (), "state the premises"),
            NodeTemplate(
                "n2",
                f"n in {{2, {divisor}}}",
                ("n1",),
                "enumerate the permitted values",
            ),
        )
        examples.append(
            (
                problem,
                correct,
                Corruption(
                    LOGICAL_INFERENCE_ERROR,
                    "unsupported_single_conclusion",
                    "n2",
                    "n = 2",
                    correct[1].state,
                ),
            )
        )
    return examples


def _semantic_examples() -> list[tuple[str, tuple[NodeTemplate, ...], Corruption]]:
    examples = []
    for threshold in [3, 4, 5, 6, 7, 8]:
        problem = f"Find integers at least {threshold}."
        correct = (
            NodeTemplate("n1", problem, (), "interpret the quantifier"),
            NodeTemplate(
                "n2", f"x >= {threshold}", ("n1",), "formalize the condition"
            ),
        )
        examples.append(
            (
                problem,
                correct,
                Corruption(
                    SEMANTIC_INTERPRETATION_ERROR,
                    "strict_quantifier",
                    "n2",
                    f"x > {threshold}",
                    correct[1].state,
                ),
            )
        )
    return examples


def generate_examples(count_per_type: int = 6, seed: int = 42) -> list[dict[str, object]]:
    """Generate a balanced, deterministic controlled-corruption dataset."""
    if count_per_type < 1 or count_per_type > 6:
        raise ValueError("count-per-type must be between 1 and 6.")
    pools = (
        _arithmetic_examples()
        + _algebraic_examples()
        + _sign_examples()
        + _incomplete_examples()
        + _dependency_examples()
        + _assumption_examples()
        + _logical_examples()
        + _semantic_examples()
    )
    grouped: dict[str, list[tuple[str, tuple[NodeTemplate, ...], Corruption]]] = {}
    for example in pools:
        grouped.setdefault(example[2].error_type, []).append(example)
    random_generator = random.Random(seed)
    examples: list[dict[str, object]] = []
    for error_type in sorted(grouped):
        candidates = list(grouped[error_type])
        random_generator.shuffle(candidates)
        for sample_index, (problem, nodes, corruption) in enumerate(
            candidates[:count_per_type], start=1
        ):
            examples.append(
                make_example(problem, nodes, corruption, sample_index)
            )
    random_generator.shuffle(examples)
    for index, example in enumerate(examples, start=1):
        example["dataset_index"] = index
    return examples


def write_dataset(
    output: Path,
    manifest: Path,
    examples: list[dict[str, object]],
    seed: int,
) -> None:
    """Write JSONL examples and a reproducibility manifest."""
    output.write_text(
        json.dumps(examples, indent=2, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )
    manifest.write_text(
        json.dumps(
            {
                "dataset": "typed_verifier_pilot",
                "source": "controlled_synthetic",
                "seed": seed,
                "example_count": len(examples),
                "error_type_counts": dict(
                    Counter(str(example["error_type"]) for example in examples)
                ),
                "sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
                "reference_solution_leakage": False,
            },
            indent=2,
            ensure_ascii=True,
        )
        + "\n",
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--count-per-type", type=int, default=6)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    args = parser.parse_args()
    try:
        examples = generate_examples(args.count_per_type, args.seed)
        write_dataset(args.output, args.manifest, examples, args.seed)
    except (OSError, ValueError, TypeError) as error:
        parser.error(str(error))
    print(f"Generated {len(examples)} typed-verifier examples: {args.output}")
    print(f"Manifest: {args.manifest}")


if __name__ == "__main__":
    main()
