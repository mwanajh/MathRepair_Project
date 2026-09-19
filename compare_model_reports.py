"""Compare two completed repeated-experiment aggregate reports."""

import argparse
import json
from pathlib import Path


STRATEGIES = (
    "no_repair",
    "verified_global_regeneration",
    "verified_local_repair",
)


def load_report(path: Path) -> dict[str, object]:
    with path.open(encoding="utf-8") as file:
        report = json.load(file)
    required = {
        "model",
        "problem_set_sha256",
        "problem_count",
        "runs_per_trial",
        "temperature",
        "samples_per_problem",
        "strategy_metrics",
    }
    missing = required - set(report)
    if missing:
        raise ValueError(f"Report {path} is missing fields: {sorted(missing)}")
    return report


def validate_comparable(baseline: dict[str, object], candidate: dict[str, object]) -> None:
    for field in (
        "problem_set_sha256",
        "problem_count",
        "runs_per_trial",
        "temperature",
        "samples_per_problem",
    ):
        if baseline[field] != candidate[field]:
            raise ValueError(
                f"Reports cannot be compared: {field} differs "
                f"({baseline[field]} vs {candidate[field]})."
            )
    for strategy in STRATEGIES:
        if strategy not in baseline["strategy_metrics"]:
            raise ValueError(f"Baseline is missing strategy {strategy}.")
        if strategy not in candidate["strategy_metrics"]:
            raise ValueError(f"Candidate is missing strategy {strategy}.")


def compare_reports(
    baseline: dict[str, object], candidate: dict[str, object]
) -> dict[str, object]:
    validate_comparable(baseline, candidate)
    strategy_differences = {}
    for strategy in STRATEGIES:
        baseline_metrics = baseline["strategy_metrics"][strategy]
        candidate_metrics = candidate["strategy_metrics"][strategy]
        strategy_differences[strategy] = {
            "answer_accuracy_difference": (
                float(candidate_metrics["answer_accuracy"]["mean"])
                - float(baseline_metrics["answer_accuracy"]["mean"])
            ),
            "trace_validity_difference": (
                float(candidate_metrics["trace_valid_rate"]["mean"])
                - float(baseline_metrics["trace_valid_rate"]["mean"])
            ),
        }
    return {
        "baseline_model": baseline["model"],
        "candidate_model": candidate["model"],
        "problem_set": baseline.get("problem_set", ""),
        "problem_set_sha256": baseline["problem_set_sha256"],
        "problem_count": baseline["problem_count"],
        "runs_per_trial": baseline["runs_per_trial"],
        "temperature": baseline["temperature"],
        "samples_per_problem": baseline["samples_per_problem"],
        "generation_failures": {
            "baseline_total": sum(
                int(trial.get("failure_count", 0))
                for trial in baseline.get("trial_summaries", [])
            ),
            "candidate_total": sum(
                int(trial.get("failure_count", 0))
                for trial in candidate.get("trial_summaries", [])
            ),
        },
        "strategy_differences": strategy_differences,
        "baseline_paired_local_minus_global": baseline[
            "paired_local_minus_global"
        ],
        "candidate_paired_local_minus_global": candidate[
            "paired_local_minus_global"
        ],
    }


def percent(value: float) -> str:
    return f"{100 * value:+.1f} pp"


def render_markdown(comparison: dict[str, object]) -> str:
    lines = [
        "# MathRepair Model Comparison",
        "",
        f"Baseline: `{comparison['baseline_model']}`",
        f"Candidate: `{comparison['candidate_model']}`",
        f"Problem set: `{comparison['problem_set']}` ({comparison['problem_count']} problems)",
        f"Temperature: `{comparison['temperature']}` | Samples/problem: `{comparison['samples_per_problem']}`",
        (
            "Generation failures: "
            f"baseline `{comparison['generation_failures']['baseline_total']}` | "
            f"candidate `{comparison['generation_failures']['candidate_total']}`"
        ),
        "",
        "Positive values mean the candidate model improved over the baseline.",
        "",
        "| Strategy | Answer accuracy difference | Trace-validity difference |",
        "|---|---:|---:|",
    ]
    for strategy, metrics in comparison["strategy_differences"].items():
        lines.append(
            f"| {strategy} | {percent(metrics['answer_accuracy_difference'])} | "
            f"{percent(metrics['trace_validity_difference'])} |"
        )
    lines.extend(
        [
            "",
            "The paired local-minus-global intervals for each model remain in the "
            "source aggregate reports; this table compares model means.",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--markdown", type=Path)
    args = parser.parse_args()
    baseline = load_report(args.baseline)
    candidate = load_report(args.candidate)
    comparison = compare_reports(baseline, candidate)
    output = args.output or args.candidate.with_name("model_comparison.json")
    markdown = args.markdown or args.candidate.with_name("model_comparison.md")
    output.write_text(
        json.dumps(comparison, indent=2, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )
    markdown.write_text(render_markdown(comparison), encoding="utf-8")
    print(f"JSON: {output}")
    print(f"Markdown: {markdown}")


if __name__ == "__main__":
    main()
