"""Replay saved failures to separate generation and reasoning losses."""

import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path

from parser_sensitivity_analysis import recover_failed_trace


def empty_category() -> dict[str, int]:
    return {
        "planned": 0,
        "completed": 0,
        "generation_failures": 0,
        "strict_answer_correct": 0,
        "strict_trace_valid": 0,
        "local_answer_correct": 0,
        "local_trace_valid": 0,
        "normalized_recovered": 0,
        "normalized_answer_correct": 0,
        "normalized_trace_valid": 0,
    }


def replay_directory(input_dir: Path) -> dict[str, object]:
    """Aggregate planned outcomes and offline recovery by category."""
    categories: dict[str, dict[str, int]] = defaultdict(empty_category)
    failure_types: Counter[str] = Counter()
    trial_count = 0
    for trial_dir in sorted(input_dir.glob("seed_*")):
        report_path = trial_dir / "repair_report.json"
        trace_path = trial_dir / "traces.jsonl"
        if not report_path.exists() or not trace_path.exists():
            continue
        trial_count += 1
        report = json.loads(report_path.read_text(encoding="utf-8"))
        failed_traces: dict[tuple[str, int], dict[str, object]] = {}
        for line in trace_path.read_text(encoding="utf-8").splitlines():
            record = json.loads(line)
            if record.get("status") != "failed":
                continue
            labels = record.get("labels", {})
            failed_traces[(str(record["problem"]), int(labels.get("seed", 0)))] = record

        for item in report.get("results", []):
            category = str(item.get("category", "unknown"))
            metrics = categories[category]
            metrics["planned"] += 1
            if item.get("status") == "completed":
                metrics["completed"] += 1
                metrics["strict_answer_correct"] += int(bool(item.get("answer_correct")))
                metrics["strict_trace_valid"] += int(bool(item.get("model_trace_valid")))
                metrics["local_answer_correct"] += int(
                    bool(item.get("post_model_repair_answer_correct", item.get("answer_correct")))
                )
                metrics["local_trace_valid"] += int(
                    bool(item.get("post_model_repair_trace_valid", item.get("model_trace_valid")))
                )
                continue

            metrics["generation_failures"] += 1
            key = (str(item.get("problem", "")), int(item.get("seed", 0)))
            failed = failed_traces.get(key, {})
            labels = failed.get("labels", {})
            recovery = recover_failed_trace(
                key[0],
                str(labels.get("expected_answer", item.get("expected_answer", ""))),
                str(failed.get("raw_response", "")),
            )
            recovery_type = str(recovery.get("error_type") or "")
            if not recovery_type:
                recovery_type = "recovered_valid_trace" if recovery.get("recovered") else "unknown"
            failure_types[recovery_type] += 1
            metrics["normalized_recovered"] += int(bool(recovery.get("recovered")))
            metrics["normalized_answer_correct"] += int(bool(recovery.get("answer_correct")))
            metrics["normalized_trace_valid"] += int(bool(recovery.get("trace_valid")))

    if not categories:
        raise ValueError(f"No trial reports found in {input_dir}.")
    return {
        "analysis": "failure_replay_by_category",
        "input_directory": str(input_dir),
        "trial_count": trial_count,
        "total_planned_runs": sum(item["planned"] for item in categories.values()),
        "failure_type_counts": dict(sorted(failure_types.items())),
        "categories": dict(sorted(categories.items())),
        "caveat": (
            "Offline replay changes parser handling only for saved generation "
            "failures; it does not rerun model generation."
        ),
    }


def percent(numerator: int, denominator: int) -> str:
    return f"{100 * numerator / denominator:.1f}%" if denominator else "0.0%"


def render_markdown(report: dict[str, object]) -> str:
    lines = [
        "# Failure Replay By Category",
        "",
        f"Trials: `{report['trial_count']}` | Planned runs: `{report['total_planned_runs']}`",
        "",
        "Rates use planned runs in each category as the denominator.",
        "",
        "| Category | Planned | Failures | Strict answer | Local answer | Normalized recovery | Normalized answer |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for category, metrics in report["categories"].items():
        planned = int(metrics["planned"])
        lines.append(
            f"| {category} | {planned} | {metrics['generation_failures']} | "
            f"{percent(metrics['strict_answer_correct'], planned)} | "
            f"{percent(metrics['local_answer_correct'], planned)} | "
            f"{percent(metrics['normalized_recovered'], metrics['generation_failures'])} | "
            f"{percent(metrics['strict_answer_correct'] + metrics['normalized_answer_correct'], planned)} |"
        )
    lines.extend(
        [
            "",
            f"Failure recovery types: `{report['failure_type_counts']}`",
            "",
            f"Caveat: {report['caveat']}",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--markdown", type=Path)
    args = parser.parse_args()
    report = replay_directory(args.input_dir)
    output = args.output or args.input_dir / "failure_replay_report.json"
    markdown = args.markdown or args.input_dir / "failure_replay_report.md"
    output.write_text(json.dumps(report, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    markdown.write_text(render_markdown(report), encoding="utf-8")
    print(f"JSON: {output}")
    print(f"Markdown: {markdown}")


if __name__ == "__main__":
    main()
