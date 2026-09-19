"""Aggregate typed error detection and repair outcomes across trials."""

import argparse
from collections import defaultdict
import json
from pathlib import Path


def collect_error_metrics(input_dir: Path) -> dict[str, dict[str, int]]:
    totals: dict[str, dict[str, int]] = defaultdict(
        lambda: {
            "detected": 0,
            "accepted_repairs": 0,
            "corrected_wrong_answers": 0,
            "repair_regressions": 0,
        }
    )
    trial_dirs = sorted(input_dir.glob("seed_*"))
    for trial_dir in trial_dirs:
        report_path = trial_dir / "repair_report.json"
        if not report_path.exists():
            continue
        with report_path.open(encoding="utf-8") as file:
            report = json.load(file)
        for item in report.get("results", []):
            if item.get("status") != "completed" or item.get("model_trace_valid"):
                continue
            error_type = str(item.get("error_type") or "unknown")
            metrics = totals[error_type]
            metrics["detected"] += 1
            accepted = bool(item.get("model_repair_accepted", False))
            post_correct = bool(
                item.get("post_model_repair_answer_correct", item.get("answer_correct"))
            )
            metrics["accepted_repairs"] += int(accepted)
            metrics["corrected_wrong_answers"] += int(
                not bool(item.get("answer_correct")) and post_correct
            )
            metrics["repair_regressions"] += int(
                bool(item.get("answer_correct"))
                and accepted
                and not post_correct
            )
    return dict(sorted(totals.items()))


def render_markdown(metrics: dict[str, dict[str, int]], input_dir: Path) -> str:
    lines = [
        "# MathRepair Typed Error Analysis",
        "",
        f"Source: `{input_dir}`",
        "",
        "| Error type | Detected | Accepted repairs | Corrected wrong answers | Regressions |",
        "|---|---:|---:|---:|---:|",
    ]
    for error_type, values in metrics.items():
        lines.append(
            f"| {error_type} | {values['detected']} | "
            f"{values['accepted_repairs']} | "
            f"{values['corrected_wrong_answers']} | "
            f"{values['repair_regressions']} |"
        )
    lines.extend(
        [
            "",
            "Interpretation: counts are aggregated across completed trial runs; "
            "they are not independent problem samples.",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--markdown", type=Path)
    args = parser.parse_args()
    metrics = collect_error_metrics(args.input_dir)
    output = args.output or args.input_dir / "error_report.json"
    markdown = args.markdown or args.input_dir / "error_report.md"
    output.write_text(json.dumps(metrics, indent=2) + "\n", encoding="utf-8")
    markdown.write_text(
        render_markdown(metrics, args.input_dir), encoding="utf-8"
    )
    print(f"JSON: {output}")
    print(f"Markdown: {markdown}")


if __name__ == "__main__":
    main()
