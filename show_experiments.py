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
            "REASONING GRAPH IN THE MODEL PIPELINE",
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
    lines = [
            "HARD BENCHMARK PILOT",
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
    accuracy_path = root / "math500_accuracy_pilot_5.json"
    if accuracy_path.exists():
        accuracy = load_report(accuracy_path)
        lines.extend(
            [
                "",
                "ANSWER-SCORED FIVE-PROBLEM PILOT",
                f"Completed: {accuracy['completed_count']}/{accuracy['problem_count']}",
                f"Initial answer accuracy: {percent(accuracy['initial_answer_accuracy'])}",
                f"Final answer accuracy: {percent(accuracy['final_answer_accuracy'])}",
                f"Repair success: {accuracy['repair_success_count']}/{accuracy['repair_attempt_count']}",
                f"Repair regressions: {accuracy['repair_regression_count']}",
                f"Model calls / tokens: {accuracy['total_model_calls']} / {accuracy['total_tokens']}",
                "This is a calibration pilot, not a 40-problem benchmark result.",
            ]
        )
    full_path = root / "math500_full40_baseline_report.json"
    if full_path.exists():
        full = load_report(full_path)
        lines.extend(
            [
                "",
                "ANSWER-SCORED FULL 40-PROBLEM BASELINE",
                f"Completed generations: {full['completed_count']}/{full['problem_count']}",
                f"Answer accuracy: {percent(full['initial_answer_accuracy'])}",
                f"Strict / normalized outputs: {full['strict_output_contract_count']} / "
                f"{full['normalized_recovery_count']}",
                f"Model calls / tokens: {full['total_model_calls']} / {full['total_tokens']}",
            ]
        )
    return "\n".join(lines)


def render_task3() -> str:
    rows = [
        [code, ", ".join(spec.recommended_actions)]
        for code, spec in ERROR_TAXONOMY.items()
    ]
    return "\n".join(
        [
            "FROZEN TYPED-ERROR TAXONOMY",
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
    lines = [
            "TYPED VERIFIER TRAINING DATA",
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
    learned_path = root / "learned_verifier_report.json"
    if learned_path.exists():
        learned = load_report(learned_path)
        test = learned["test_metrics"]
        baseline = learned["test_rule_baseline"]
        lines.extend(
            [
                "",
                "LEARNED VERIFIER HELD-OUT PILOT",
                f"Split: {learned['split']['train']['count']}/"
                f"{learned['split']['dev']['count']}/"
                f"{learned['split']['test']['count']} train/dev/test",
                f"Location accuracy: {percent(test['error_location_accuracy'])}",
                f"Error-type accuracy: {percent(test['error_type_accuracy'])}",
                f"Rule/symbolic baseline coverage: {percent(baseline['coverage'])}",
                "Synthetic templates only; natural-trace generalization is not established.",
            ]
        )
    return "\n".join(lines)


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
            "MATCHED-BUDGET EXPERIMENT",
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
            "ABLATION TABLE",
            table(
                ["Variant", "Status", "Answer", "Valid trace", "Repair"],
                rows,
            ),
            "",
            "Note: '--' avoids mixing metrics from the separate MATH-500 protocol.",
            "Full MathRepair remains a rule-based proxy only within the equation table.",
        ]
    )


def render_verifier_ablation(root: Path) -> str:
    path = root / "verifier_ablation_report.json"
    if not path.exists():
        return ""
    report = load_report(path)
    rows = []
    for variant in report["variants"]:
        metrics = variant["metrics"]
        rows.append(
            [
                variant["variant_id"],
                percent(metrics["error_location_accuracy"]),
                percent(metrics["error_type_accuracy"]),
                percent(metrics["end_to_end_accuracy"]),
            ]
        )
    return "\n".join(
        [
            "VERIFIER-STAGE ABLATIONS",
            table(["Variant", "Location", "Type", "End to end"], rows),
            "Eight synthetic held-out examples; these are not answer-accuracy ablations.",
        ]
    )


def render_system_ablation(root: Path) -> str:
    path = root / "math500_system_ablation_report.json"
    if not path.exists():
        return ""
    report = load_report(path)
    rows = []
    for variant in report["variants"]:
        rows.append(
            [
                variant["variant_id"],
                percent(variant["initial_answer_accuracy"]),
                percent(variant["final_answer_accuracy"]),
                variant["verifier_detection_count"],
                f"{variant['repair_success_count']}/{variant['repair_attempt_count']}",
                variant["repair_regression_count"],
                variant["budget_skipped_count"],
                variant["additional_model_calls"],
                variant["additional_tokens"],
            ]
        )
    return "\n".join(
        [
            "MATH-500 SYSTEM-LEVEL ABLATIONS",
            f"Shared additional-token ceiling: {report['matched_additional_token_budget']}",
            table(
                [
                    "Variant",
                    "Initial",
                    "Final",
                    "Detect",
                    "Repair",
                    "Regress",
                    "Skipped",
                    "Calls",
                    "Tokens",
                ],
                rows,
            ),
            "Baseline generations are identical across arms; failures remain in the denominator.",
            report["symbolic_support_observation"],
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
            "OUTPUT-CONTRACT SENSITIVITY",
            table(
                ["Model", "Prompt", "Failures", "Strict", "Normalized", "Delta"],
                rows,
            ),
            "",
            "Note: normalized accuracy is parser-only sensitivity, not the primary result.",
            f"Saved raw-output records: {report['raw_output_archive']['record_count']}",
        ]
    )


def render_task8(root: Path) -> str:
    report = load_report(root / "learned_verifier_report.json")
    test = report["test_metrics"]
    baseline = report["test_rule_baseline"]
    split = report["split"]
    return "\n".join(
        [
            "LEARNED TYPED VERIFIER",
            "Saved experiment result: TF-IDF + logistic regression",
            f"Controlled examples: {report['dataset']['example_count']}",
            "Train / development / test: "
            f"{split['train']['count']} / {split['dev']['count']} / {split['test']['count']}",
            "",
            table(
                ["Method", "First-error location", "Error type", "Coverage"],
                [
                    ["Learned verifier", percent(test["error_location_accuracy"]),
                     percent(test["error_type_accuracy"]), "100.0%"],
                    ["Rule/symbolic baseline",
                     percent(baseline["error_location_accuracy_with_abstentions_wrong"]),
                     percent(baseline["error_type_accuracy_with_abstentions_wrong"]),
                     percent(baseline["coverage"])],
                ],
            ),
            "",
            "Test set has eight synthetic examples; natural-trace accuracy is unproven.",
        ]
    )


def render_task9(root: Path) -> str:
    report = load_report(root / "math500_full40_baseline_report.json")
    return "\n".join(
        [
            "MATH-500 ANSWER-SCORED EVALUATION",
            f"Benchmark: {report['benchmark']} | Model: {report['model']}",
            "Saved result; reference answers used after generation for scoring.",
            "",
            table(
                ["Metric", "Result"],
                [
                    ["Problems", report["problem_count"]],
                    ["Completed generations", report["completed_count"]],
                    ["Output failures", report["failure_count"]],
                    ["Correct answers", report["final_answer_correct_count"]],
                    ["Answer accuracy (all 40)", percent(report["final_answer_accuracy"])],
                    ["Strict / normalized outputs",
                     f"{report['strict_output_contract_count']} / {report['normalized_recovery_count']}"],
                    ["Model calls / tokens",
                     f"{report['total_model_calls']} / {report['total_tokens']:,}"],
                ],
            ),
            "",
            "All ten output failures remain in the accuracy denominator.",
        ]
    )


def render_task10(root: Path) -> str:
    report = load_report(root / "math500_system_ablation_report.json")
    full = next(
        variant for variant in report["variants"]
        if variant["variant_id"] == "full_mathrepair"
    )
    return "\n".join(
        [
            "MATCHED-BUDGET SYSTEM ABLATIONS",
            "Saved experiment result; same baseline generations across variants.",
            f"Shared additional-token ceiling: {report['matched_additional_token_budget']:,}",
            "",
            table(
                ["Variant", "Initial", "Final", "Detected", "Fixed", "Regressed", "Tokens"],
                [
                    [variant["variant_id"],
                     percent(variant["initial_answer_accuracy"]),
                     percent(variant["final_answer_accuracy"]),
                     variant["verifier_detection_count"],
                     f"{variant['repair_success_count']}/{variant['repair_attempt_count']}",
                     variant["repair_regression_count"],
                     variant["additional_tokens"]]
                    for variant in report["variants"]
                ],
            ),
            "",
            f"Full system: {full['repair_success_count']} successful repair and "
            f"{full['repair_regression_count']} regressions; final accuracy "
            f"{percent(full['final_answer_accuracy'])}.",
            "The symbolic heuristic abstained on every completed open-ended trace.",
            "These are pilot results; component value is not established.",
        ]
    )


def render_task11(root: Path) -> str:
    report = load_report(root / "error_category_analysis.json")

    def result(row: dict[str, object], prefix: str) -> str:
        if row["observed_error_runs"] == 0:
            return "--"
        return (f"{row[prefix + '_success_count']}/{row['observed_error_runs']} "
                f"({percent(row[prefix + '_success_rate'])})")

    rows = [
        [row["error_category"], row["observed_error_runs"],
         result(row, "global"), result(row, "uniform_local"),
         result(row, "adaptive_local"),
         ("--" if row["observed_error_runs"] == 0 else
          "none succeeded" if max(row["global_success_count"],
                                  row["uniform_local_success_count"],
                                  row["adaptive_local_success_count"]) == 0 else
          "global/adaptive tie" if row["best_observed_strategy"] == "tie" else
          str(row["best_observed_strategy"]))]
        for row in report["rows"]
    ]
    return "\n".join(
        [
            "ERROR-CATEGORY REPAIR ANALYSIS",
            f"Detected-error runs: {report['detected_error_run_count']}",
            "Accepted, answer-correct repairs in the matched-budget pilot:",
            "",
            table(["Error category", "Cases", "Global", "Uniform local",
                   "Adaptive local", "Best observed"], rows),
            "",
            "Global regeneration was stronger for observed algebraic errors (2/5).",
            "The sign-error comparison has only one case; five categories had no cases.",
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
        "task8": lambda: render_task8(root),
        "task9": lambda: render_task9(root),
        "task10": lambda: render_task10(root),
        "task11": lambda: render_task11(root),
    }
    selected = list(renderers) if section == "all" else [section]
    blocks = ["MATHREPAIR EXPERIMENT RESULTS"]
    for name in selected:
        blocks.append(renderers[name]())
        if name == "task6":
            system_ablation = render_system_ablation(root)
            if system_ablation:
                blocks.append(system_ablation)
            verifier_ablation = render_verifier_ablation(root)
            if verifier_ablation:
                blocks.append(verifier_ablation)
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
            "task8",
            "task9",
            "task10",
            "task11",
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
