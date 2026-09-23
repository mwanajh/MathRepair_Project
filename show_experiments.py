"""Show the current MathRepair experiment results in the terminal."""

import argparse
import json
from pathlib import Path

from error_taxonomy import ERROR_TAXONOMY
from model_pipeline import MockMathModel, run_pipeline
from reasoning_graph import serialize_reasoning_node


PROJECT_DIR = Path(__file__).resolve().parent


def load_report(path: Path) -> dict[str, object]:
    if not path.exists():
        raise ValueError(f"Report not found: {path}. Run its generator first.")
    report = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(report, dict):
        raise ValueError(f"Expected a JSON object: {path}")
    return report


def percent(value: object) -> str:
    return "--" if value is None else f"{100 * float(value):.1f}%"


def number(value: object, digits: int = 2) -> str:
    return "--" if value is None else f"{float(value):.{digits}f}"


def table(headers: list[str], rows: list[list[object]]) -> str:
    text_rows = [[str(value) for value in row] for row in rows]
    widths = [len(header) for header in headers]
    for row in text_rows:
        if len(row) != len(headers):
            raise ValueError("Table row does not match the header count.")
        widths = [
            max(width, len(value))
            for width, value in zip(widths, row)
        ]

    def render_row(row: list[str]) -> str:
        return " | ".join(
            value.ljust(width) for value, width in zip(row, widths)
        )

    separator = "-+-".join("-" * width for width in widths)
    return "\n".join(
        [render_row(headers), separator]
        + [render_row(row) for row in text_rows]
    )


def render_task1() -> str:
    result = run_pipeline(
        "2(x + 3) = 14",
        MockMathModel(),
        provider="mock",
        model_name="deliberate-error-mock",
    )
    rows = []
    for node in result.reasoning_graph:
        record = serialize_reasoning_node(node)
        rows.append(
            [
                record["node_id"],
                ",".join(record["parent_dependency"]) or "--",
                record["reasoning_state"],
                "PASS" if record["verification_result"] else "ERROR",
                record["error_type"] or "--",
                record["repair_action"] or "--",
                record["repaired_state"] or "--",
                record["final_status"],
            ]
        )
    return "\n".join(
        [
            "TASK 1 - REASONING GRAPH IN THE MODEL PIPELINE",
            f"Problem: {result.problem}",
            "Offline demonstration; the Ollama model uses this same graph path.",
            "",
            table(
                [
                    "Node",
                    "Parent",
                    "Reasoning state",
                    "Check",
                    "Error type",
                    "Repair action",
                    "Repaired state",
                    "Final status",
                ],
                rows,
            ),
            "",
            f"Affected descendants: {', '.join(result.analysis.affected_node_ids)}",
            f"Final verified answer: {result.analysis.correct_answer}",
        ]
    )


def render_task2(root: Path) -> str:
    manifest = load_report(root / "math500_pilot_40_manifest.json")
    pilot_run = load_report(root / "math500_pilot_run.json")
    processed = sum(bool(item["processed"]) for item in pilot_run["results"])
    rows = [
        [subject, quota]
        for subject, quota in manifest["subject_quotas"].items()
    ]
    return "\n".join(
        [
            "TASK 2 - HARD BENCHMARK PILOT",
            f"Benchmark: {manifest['benchmark']}",
            f"Selected problems: {manifest['problem_count']}",
            f"Difficulty levels: {manifest['level_counts']}",
            f"Pipeline smoke test processed: {processed}/{pilot_run['problem_count']}",
            f"Verification mode: {pilot_run['verification_mode']}",
            "",
            table(["Subject", "Problems"], rows),
            "",
            "Note: text_unverified is a processing smoke test, not an accuracy result.",
        ]
    )


def render_task3() -> str:
    rows = [
        [code, ", ".join(spec.recommended_actions)]
        for code, spec in ERROR_TAXONOMY.items()
    ]
    return "\n".join(
        [
            "TASK 3 - FROZEN TYPED-ERROR TAXONOMY",
            f"Frozen error types: {len(ERROR_TAXONOMY)}",
            "",
            table(["Error type", "Recommended repair actions"], rows),
            "",
            "Full definitions and examples: ERROR_TAXONOMY.md",
        ]
    )


def render_task4(root: Path) -> str:
    manifest = load_report(root / "typed_verifier_pilot_manifest.json")
    examples = json.loads(
        (root / "typed_verifier_pilot.json").read_text(encoding="utf-8")
    )
    rows = [
        [
            example["error_location"],
            example["error_type"],
            example["corrupted_step"],
            example["correct_step"],
            example["preferred_repair_action"],
        ]
        for example in examples[:4]
    ]
    return "\n".join(
        [
            "TASK 4 - TYPED VERIFIER TRAINING DATA",
            f"Dataset examples: {manifest['example_count']}",
            f"Examples per error type: {set(manifest['error_type_counts'].values()).pop()}",
            f"Reference-answer leakage: {manifest['reference_solution_leakage']}",
            "",
            table(
                ["Node", "Error type", "Corrupted step", "Correct step", "Repair"],
                rows,
            ),
            "",
            "The table shows the first four controlled-corruption examples.",
        ]
    )


def render_task5(report: dict[str, object]) -> str:
    names = {
        "no_repair": "No repair",
        "verified_global_regeneration": "Global regeneration",
        "verified_local_repair_uniform": "Uniform local repair",
        "verified_local_repair_adaptive": "Adaptive local repair",
    }
    rows = []
    for strategy in report["strategies"]:
        name = str(strategy["name"])
        rows.append(
            [
                names.get(name, name),
                percent(strategy["answer_accuracy"]),
                percent(strategy["trace_valid_rate"]),
                percent(strategy["repair_success_rate"]),
                number(strategy["average_model_calls"]),
                number(strategy["average_tokens"], 1),
            ]
        )
    difference = report[
        "answer_accuracy_difference_vs_global_percentage_points"
    ]["verified_local_repair_adaptive"]
    return "\n".join(
        [
            "TASK 5 - MATCHED-BUDGET EXPERIMENT",
            f"Matched additional-token ceiling: {report['matched_additional_token_budget']:,}",
            "",
            table(
                ["Strategy", "Answer", "Valid trace", "Repair", "Avg calls", "Avg tokens"],
                rows,
            ),
            "",
            (
                "Result: adaptive local repair was "
                f"{float(difference):+.1f} percentage points versus global regeneration."
            ),
        ]
    )


def render_task6(report: dict[str, object]) -> str:
    rows = []
    for row in report["rows"]:
        metrics = row["metrics"]
        rows.append(
            [
                row["variant"],
                row["status"],
                percent(metrics["answer_accuracy"]),
                percent(metrics["trace_valid_rate"]),
                percent(metrics["repair_success_rate"]),
            ]
        )
    return "\n".join(
        [
            "TASK 6 - ABLATION TABLE",
            table(
                ["Variant", "Status", "Answer", "Valid trace", "Repair"],
                rows,
            ),
            "",
            "Note: '--' means the experiment is planned but has not been run.",
            "Full MathRepair is currently a rule-based proxy, not the final learned verifier.",
        ]
    )


def render_task7(report: dict[str, object]) -> str:
    rows = []
    for row in report["experiments"]:
        rows.append(
            [
                row["model_version"]["ollama_tag"],
                row["prompt_profile"],
                row["generation_failure_count"],
                percent(row["strict_answer_accuracy"]),
                percent(row["normalized_answer_accuracy"]),
                f"{float(row['normalization_delta_percentage_points']):+.1f} pp",
            ]
        )
    return "\n".join(
        [
            "TASK 7 - OUTPUT-CONTRACT SENSITIVITY",
            table(
                ["Model", "Prompt", "Failures", "Strict", "Normalized", "Delta"],
                rows,
            ),
            "",
            "Note: normalized accuracy is parser-only sensitivity, not the primary result.",
            f"Saved raw-output records: {report['raw_output_archive']['record_count']}",
        ]
    )


def build_display(section: str, root: Path = PROJECT_DIR) -> str:
    renderers = {
        "task1": lambda: render_task1(),
        "task2": lambda: render_task2(root),
        "task3": lambda: render_task3(),
        "task4": lambda: render_task4(root),
        "task5": lambda: render_task5(
            load_report(root / "matched_budget_report.json")
        ),
        "task6": lambda: render_task6(load_report(root / "ablation_table.json")),
        "task7": lambda: render_task7(
            load_report(root / "output_contract_evidence.json")
        ),
    }
    selected = list(renderers) if section == "all" else [section]
    blocks = ["MATHREPAIR EXPERIMENT RESULTS"]
    for name in selected:
        blocks.append(renderers[name]())
    return "\n\n".join(blocks)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--section",
        choices=[
            "all",
            "task1",
            "task2",
            "task3",
            "task4",
            "task5",
            "task6",
            "task7",
        ],
        default="all",
        help="Choose one experiment section or show all sections.",
    )
    args = parser.parse_args()
    try:
        print(build_display(args.section))
    except (OSError, ValueError, KeyError, TypeError) as error:
        parser.error(str(error))


if __name__ == "__main__":
    main()
