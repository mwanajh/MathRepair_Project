"""Summarize baseline and repair results for research reporting."""

import argparse
from collections import defaultdict
from datetime import datetime, timezone
import json
from pathlib import Path

from collect_model_traces import answers_match
from model_pipeline import select_model_answer_step


DEFAULT_REPORT = Path(__file__).with_name("stress_multisample_report.json")
DEFAULT_JSON = Path(__file__).with_name("repair_experiment_summary.json")
DEFAULT_MARKDOWN = Path(__file__).with_name("repair_experiment_summary.md")
DEFAULT_MATCHED_REPORT = Path(__file__).with_name("matched_budget_report.json")


def safe_rate(numerator: int, denominator: int) -> float:
    """Return a zero-safe fraction in the range normally used by metrics."""
    return numerator / denominator if denominator else 0.0


def repaired_answer_correct(record: dict[str, object], steps_key: str) -> bool:
    """Evaluate a repaired chain's selected final answer."""
    steps = record.get(steps_key, [])
    if not isinstance(steps, list) or not steps:
        return bool(record.get("answer_correct", False))
    problem = str(record["problem"])
    expected = str(record["expected_answer"])
    answer = select_model_answer_step(problem, [str(step) for step in steps])
    return answers_match(expected, answer)


def build_experiment_summary(
    report: dict[str, object],
    matched_report: dict[str, object] | None = None,
) -> dict[str, object]:
    """Build comparable strategy, repair, efficiency, and category metrics."""
    results = [
        item
        for item in report.get("results", [])
        if item.get("status") == "completed"
    ]
    if not results:
        raise ValueError("Report contains no completed experiment results.")

    total = len(results)
    baseline_answer_correct = sum(bool(item["answer_correct"]) for item in results)
    baseline_trace_valid = sum(bool(item["model_trace_valid"]) for item in results)

    symbolic_answer_correct = 0
    symbolic_trace_valid = 0
    model_answer_correct = 0
    model_trace_valid = 0
    for item in results:
        baseline_valid = bool(item["model_trace_valid"])
        symbolic_success = bool(item.get("auto_repair_success", False))
        model_accepted = bool(item.get("model_repair_accepted", False))

        symbolic_trace_valid += int(baseline_valid or symbolic_success)
        if symbolic_success and not baseline_valid:
            symbolic_answer_correct += int(
                repaired_answer_correct(item, "repaired_steps")
            )
        else:
            symbolic_answer_correct += int(bool(item["answer_correct"]))

        model_trace_valid += int(baseline_valid or model_accepted)
        if model_accepted:
            model_answer_correct += int(
                repaired_answer_correct(item, "model_repaired_steps")
            )
        else:
            model_answer_correct += int(bool(item["answer_correct"]))

    detected_errors = sum(not bool(item["model_trace_valid"]) for item in results)
    model_repair_runs = [
        item for item in results if bool(item.get("model_repair_attempted", False))
    ]
    candidate_calls = sum(
        int(item.get("model_repair_attempt_count", 0))
        for item in model_repair_runs
    )
    accepted_repairs = sum(
        bool(item.get("model_repair_accepted", False))
        for item in model_repair_runs
    )
    wrong_before = total - baseline_answer_correct
    corrected_wrong = sum(
        not bool(item["answer_correct"])
        and (
            repaired_answer_correct(item, "model_repaired_steps")
            if bool(item.get("model_repair_accepted", False))
            else False
        )
        for item in results
    )
    regressions = sum(
        bool(item["answer_correct"])
        and bool(item.get("model_repair_accepted", False))
        and not repaired_answer_correct(item, "model_repaired_steps")
        for item in results
    )

    base_prompt_tokens = sum(
        int(item.get("generation_metadata", {}).get("prompt_eval_count", 0))
        for item in results
    )
    base_completion_tokens = sum(
        int(item.get("generation_metadata", {}).get("eval_count", 0))
        for item in results
    )
    if not base_completion_tokens:
        base_completion_tokens = int(report.get("total_eval_tokens", 0))

    repair_prompt_tokens = sum(
        int(attempt.get("generation_metadata", {}).get("prompt_eval_count", 0))
        for item in model_repair_runs
        for attempt in item.get("model_repair_attempts", [])
    )
    repair_completion_tokens = sum(
        int(attempt.get("generation_metadata", {}).get("eval_count", 0))
        for item in model_repair_runs
        for attempt in item.get("model_repair_attempts", [])
    )
    if not repair_completion_tokens:
        repair_completion_tokens = int(report.get("model_repair_eval_tokens", 0))
    base_tokens = base_prompt_tokens + base_completion_tokens
    repair_tokens = repair_prompt_tokens + repair_completion_tokens
    base_calls = total
    total_calls = base_calls + candidate_calls

    category_accumulator: dict[str, dict[str, int]] = defaultdict(
        lambda: {
            "runs": 0,
            "baseline_answer_correct": 0,
            "model_answer_correct": 0,
            "baseline_trace_valid": 0,
            "model_trace_valid": 0,
        }
    )
    error_accumulator: dict[str, dict[str, int]] = defaultdict(
        lambda: {"detected": 0, "accepted": 0, "corrected_wrong": 0}
    )
    for item in results:
        category = str(item["category"])
        category_metrics = category_accumulator[category]
        category_metrics["runs"] += 1
        category_metrics["baseline_answer_correct"] += int(
            bool(item["answer_correct"])
        )
        category_metrics["baseline_trace_valid"] += int(
            bool(item["model_trace_valid"])
        )
        accepted = bool(item.get("model_repair_accepted", False))
        post_answer = (
            repaired_answer_correct(item, "model_repaired_steps")
            if accepted
            else bool(item["answer_correct"])
        )
        category_metrics["model_answer_correct"] += int(post_answer)
        category_metrics["model_trace_valid"] += int(
            bool(item["model_trace_valid"]) or accepted
        )

        if not bool(item["model_trace_valid"]):
            error_type = str(item.get("error_type") or "unknown")
            error_metrics = error_accumulator[error_type]
            error_metrics["detected"] += 1
            error_metrics["accepted"] += int(accepted)
            error_metrics["corrected_wrong"] += int(
                not bool(item["answer_correct"]) and post_answer
            )

    strategies = [
        {
            "name": "no_repair",
            "answer_correct": baseline_answer_correct,
            "answer_accuracy": safe_rate(baseline_answer_correct, total),
            "trace_valid": baseline_trace_valid,
            "trace_valid_rate": safe_rate(baseline_trace_valid, total),
            "model_calls": base_calls,
            "inference_tokens": base_tokens,
            "prompt_tokens": base_prompt_tokens,
            "completion_tokens": base_completion_tokens,
        },
        {
            "name": "symbolic_oracle_repair",
            "answer_correct": symbolic_answer_correct,
            "answer_accuracy": safe_rate(symbolic_answer_correct, total),
            "trace_valid": symbolic_trace_valid,
            "trace_valid_rate": safe_rate(symbolic_trace_valid, total),
            "model_calls": base_calls,
            "inference_tokens": base_tokens,
            "prompt_tokens": base_prompt_tokens,
            "completion_tokens": base_completion_tokens,
        },
        {
            "name": "verified_model_repair",
            "answer_correct": model_answer_correct,
            "answer_accuracy": safe_rate(model_answer_correct, total),
            "trace_valid": model_trace_valid,
            "trace_valid_rate": safe_rate(model_trace_valid, total),
            "model_calls": total_calls,
            "inference_tokens": base_tokens + repair_tokens,
            "prompt_tokens": base_prompt_tokens + repair_prompt_tokens,
            "completion_tokens": (
                base_completion_tokens + repair_completion_tokens
            ),
        },
    ]

    matched_available = bool(
        matched_report
        and matched_report.get("matched_budget_comparison_valid", False)
    )
    caveats = [
        "This is a small 12-problem stress set, not a benchmark result.",
        "Symbolic oracle repair uses verifier-derived correct states.",
        "Symbolic tool runtime is not converted into token cost.",
        "Ollama GPU sampling may vary slightly even with recorded seeds.",
    ]
    if not matched_available:
        caveats.append(
            "Strategies have not yet been compared under matched token budgets."
        )

    summary = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "source": {
            "model": report.get("model", ""),
            "runs": total,
            "problem_count": report.get("problem_count", 0),
            "samples_per_problem": report.get("samples_per_problem", 0),
            "temperature": report.get("temperature", 0.0),
            "base_seed": report.get("base_seed", 0),
        },
        "strategies": strategies,
        "repair_metrics": {
            "detected_error_runs": detected_errors,
            "model_repair_candidate_calls": candidate_calls,
            "model_repair_accepted": accepted_repairs,
            "model_repair_accept_rate": safe_rate(
                accepted_repairs, len(model_repair_runs)
            ),
            "average_candidate_calls_per_detected_error": safe_rate(
                candidate_calls, detected_errors
            ),
            "wrong_answers_before_repair": wrong_before,
            "wrong_answers_corrected": corrected_wrong,
            "wrong_answer_recovery_rate": safe_rate(
                corrected_wrong, wrong_before
            ),
            "answer_regressions": regressions,
        },
        "efficiency_metrics": {
            "base_prompt_tokens": base_prompt_tokens,
            "base_completion_tokens": base_completion_tokens,
            "base_total_inference_tokens": base_tokens,
            "model_repair_prompt_tokens": repair_prompt_tokens,
            "model_repair_completion_tokens": repair_completion_tokens,
            "model_repair_total_inference_tokens": repair_tokens,
            "repair_token_overhead_rate": safe_rate(repair_tokens, base_tokens),
            "base_model_calls": base_calls,
            "total_model_calls_with_repair": total_calls,
            "repair_call_overhead_rate": safe_rate(candidate_calls, base_calls),
            "average_repair_tokens_per_detected_error": safe_rate(
                repair_tokens, detected_errors
            ),
            "repair_tokens_per_corrected_wrong_answer": safe_rate(
                repair_tokens, corrected_wrong
            ),
            "corrected_wrong_answers_per_1000_repair_tokens": (
                safe_rate(corrected_wrong * 1000, repair_tokens)
            ),
            "answer_accuracy_gain_percentage_points": 100
            * safe_rate(model_answer_correct - baseline_answer_correct, total),
            "trace_validity_gain_percentage_points": 100
            * safe_rate(model_trace_valid - baseline_trace_valid, total),
        },
        "category_metrics": dict(sorted(category_accumulator.items())),
        "error_type_metrics": dict(sorted(error_accumulator.items())),
        "matched_budget_comparison_available": matched_available,
        "caveats": caveats,
    }
    if matched_available:
        summary["matched_budget_results"] = {
            "budget_definition": matched_report["budget_definition"],
            "global_budget_utilization_rate": matched_report[
                "global_budget_utilization_rate"
            ],
            "budget_violation_count": matched_report["budget_violation_count"],
            "strategies": matched_report["strategies"],
        }
    return summary


def percent(value: float) -> str:
    """Format a fractional metric as a percentage."""
    return f"{100 * value:.1f}%"


def render_markdown(summary: dict[str, object]) -> str:
    """Render the summary as compact research-report tables."""
    source = summary["source"]
    lines = [
        "# MathRepair Repair Experiment Summary",
        "",
        (
            f"Model: `{source['model']}` | Runs: {source['runs']} | "
            f"Problems: {source['problem_count']} | "
            f"Samples/problem: {source['samples_per_problem']}"
        ),
        "",
        "## Strategy Comparison",
        "",
        "| Strategy | Answer accuracy | Valid traces | Model calls | Tokens |",
        "|---|---:|---:|---:|---:|",
    ]
    for strategy in summary["strategies"]:
        lines.append(
            f"| {strategy['name']} | {percent(strategy['answer_accuracy'])} "
            f"({strategy['answer_correct']}/{source['runs']}) | "
            f"{percent(strategy['trace_valid_rate'])} "
            f"({strategy['trace_valid']}/{source['runs']}) | "
            f"{strategy['model_calls']} | {strategy['inference_tokens']:,} |"
        )

    repair = summary["repair_metrics"]
    efficiency = summary["efficiency_metrics"]
    lines.extend(
        [
            "",
            "## Repair Metrics",
            "",
            "| Metric | Value |",
            "|---|---:|",
            f"| Detected error runs | {repair['detected_error_runs']} |",
            (
                "| Accepted model repairs | "
                f"{repair['model_repair_accepted']}/"
                f"{repair['detected_error_runs']} "
                f"({percent(repair['model_repair_accept_rate'])}) |"
            ),
            (
                "| Wrong-answer recovery | "
                f"{repair['wrong_answers_corrected']}/"
                f"{repair['wrong_answers_before_repair']} "
                f"({percent(repair['wrong_answer_recovery_rate'])}) |"
            ),
            f"| Answer regressions | {repair['answer_regressions']} |",
            (
                "| Average candidate calls/error | "
                f"{repair['average_candidate_calls_per_detected_error']:.2f} |"
            ),
            "",
            "## Compute Efficiency",
            "",
            "| Metric | Value |",
            "|---|---:|",
            (
                "| Repair total-token overhead | "
                f"{percent(efficiency['repair_token_overhead_rate'])} |"
            ),
            (
                "| Repair call overhead | "
                f"{percent(efficiency['repair_call_overhead_rate'])} |"
            ),
            (
                "| Repair total tokens/corrected wrong answer | "
                f"{efficiency['repair_tokens_per_corrected_wrong_answer']:.1f} |"
            ),
            (
                "| Answer accuracy gain | "
                f"{efficiency['answer_accuracy_gain_percentage_points']:.1f} pp |"
            ),
            (
                "| Trace-validity gain | "
                f"{efficiency['trace_validity_gain_percentage_points']:.1f} pp |"
            ),
            "",
            "## Results By Error Type",
            "",
            "| Error type | Detected | Accepted repair | Corrected wrong |",
            "|---|---:|---:|---:|",
        ]
    )
    for error_type, metrics in summary["error_type_metrics"].items():
        lines.append(
            f"| {error_type} | {metrics['detected']} | "
            f"{metrics['accepted']} | {metrics['corrected_wrong']} |"
        )

    lines.extend(
        [
            "",
            "## Results By Category",
            "",
            (
                "| Category | Runs | Answer before | Answer after | "
                "Trace before | Trace after |"
            ),
            "|---|---:|---:|---:|---:|---:|",
        ]
    )
    for category, metrics in summary["category_metrics"].items():
        runs = metrics["runs"]
        lines.append(
            f"| {category} | {runs} | "
            f"{metrics['baseline_answer_correct']}/{runs} | "
            f"{metrics['model_answer_correct']}/{runs} | "
            f"{metrics['baseline_trace_valid']}/{runs} | "
            f"{metrics['model_trace_valid']}/{runs} |"
        )

    if summary["matched_budget_comparison_available"]:
        matched = summary["matched_budget_results"]
        lines.extend(
            [
                "",
                "## Matched-Budget Comparison",
                "",
                f"Budget rule: {matched['budget_definition']}",
                "",
                (
                    "| Strategy | Answer accuracy | Valid traces | "
                    "Extra calls | Extra tokens |"
                ),
                "|---|---:|---:|---:|---:|",
            ]
        )
        for strategy in matched["strategies"]:
            lines.append(
                f"| {strategy['name']} | "
                f"{percent(strategy['answer_accuracy'])} | "
                f"{percent(strategy['trace_valid_rate'])} | "
                f"{strategy['additional_model_calls']} | "
                f"{strategy['additional_tokens']:,} |"
            )
        lines.extend(
            [
                "",
                (
                    "Global budget utilization: "
                    f"{percent(matched['global_budget_utilization_rate'])}"
                ),
            ]
        )

    lines.extend(["", "## Caveats", ""])
    lines.extend(f"- {item}" for item in summary["caveats"])
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--json", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--markdown", type=Path, default=DEFAULT_MARKDOWN)
    parser.add_argument(
        "--matched-report", type=Path, default=DEFAULT_MATCHED_REPORT
    )
    args = parser.parse_args()

    with args.report.open(encoding="utf-8") as file:
        report = json.load(file)
    matched_report = None
    if args.matched_report.exists():
        with args.matched_report.open(encoding="utf-8") as file:
            matched_report = json.load(file)
    summary = build_experiment_summary(report, matched_report)
    args.json.write_text(
        json.dumps(summary, indent=2, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )
    args.markdown.write_text(render_markdown(summary), encoding="utf-8")

    baseline, _, model_repair = summary["strategies"]
    print("=== MathRepair Research Evaluation ===")
    print(f"Source report: {args.report}")
    print(
        "Answer accuracy: "
        f"{percent(baseline['answer_accuracy'])} -> "
        f"{percent(model_repair['answer_accuracy'])}"
    )
    print(
        "Valid traces: "
        f"{percent(baseline['trace_valid_rate'])} -> "
        f"{percent(model_repair['trace_valid_rate'])}"
    )
    print(
        "Repair total-token overhead: "
        f"{percent(summary['efficiency_metrics']['repair_token_overhead_rate'])}"
    )
    matched_status = (
        "AVAILABLE"
        if summary["matched_budget_comparison_available"]
        else "NOT YET MEASURED"
    )
    print(f"Matched-budget comparison: {matched_status}")
    print(f"JSON: {args.json}")
    print(f"Markdown: {args.markdown}")


if __name__ == "__main__":
    main()
