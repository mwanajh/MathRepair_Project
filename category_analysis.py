"""Aggregate repair accuracy by mathematical problem category."""

import argparse
from collections import defaultdict
import json
from pathlib import Path

from run_repeated_experiments import metric_text, summarize_values


DEFAULT_DIR = Path(__file__).with_name("repeated_experiments")


def completed_results(report: dict[str, object]) -> list[dict[str, object]]:
    return [
        item
        for item in report.get("results", [])
        if item.get("status") == "completed"
    ]


def category_trial_metrics(
    repair_report: dict[str, object], matched_report: dict[str, object]
) -> dict[str, dict[str, object]]:
    """Return per-category counts using all planned runs as denominators.

    Generation failures are retained as incorrect and invalid outcomes so
    categories remain comparable across trials with different failure counts.
    """
    results = list(repair_report.get("results", []))
    global_by_key = {
        (str(item["problem"]), int(item["seed"])): item
        for item in matched_report.get("global_regeneration_results", [])
    }
    categories: dict[str, dict[str, int]] = defaultdict(
        lambda: {
            "runs": 0,
            "baseline_answer_correct": 0,
            "local_answer_correct": 0,
            "global_answer_correct": 0,
            "baseline_trace_valid": 0,
            "local_trace_valid": 0,
            "global_trace_valid": 0,
        }
    )
    for item in results:
        category = str(item["category"])
        metrics = categories[category]
        metrics["runs"] += 1
        baseline_answer = bool(item.get("answer_correct", False))
        baseline_trace = bool(item.get("model_trace_valid", False))
        local_answer = bool(
            item.get("post_model_repair_answer_correct", baseline_answer)
        )
        local_trace = bool(
            item.get("post_model_repair_trace_valid", baseline_trace)
        )
        global_result = global_by_key.get(
            (str(item["problem"]), int(item["seed"]))
        )
        if global_result is None:
            global_answer = baseline_answer
            global_trace = baseline_trace
        else:
            global_answer = bool(global_result["post_global_answer_correct"])
            global_trace = bool(global_result["post_global_trace_valid"])

        metrics["baseline_answer_correct"] += int(baseline_answer)
        metrics["local_answer_correct"] += int(local_answer)
        metrics["global_answer_correct"] += int(global_answer)
        metrics["baseline_trace_valid"] += int(baseline_trace)
        metrics["local_trace_valid"] += int(local_trace)
        metrics["global_trace_valid"] += int(global_trace)
    return dict(categories)


def aggregate_category_metrics(
    trial_data: list[tuple[int, dict[str, object], dict[str, object]]]
) -> dict[str, object]:
    if len(trial_data) < 2:
        raise ValueError("Category aggregation requires at least two trials.")
    per_trial = {
        seed: category_trial_metrics(repair, matched)
        for seed, repair, matched in trial_data
    }
    category_names = sorted(
        {category for data in per_trial.values() for category in data}
    )
    output: dict[str, object] = {}
    for category in category_names:
        trial_metrics = [data[category] for data in per_trial.values()]
        runs = {int(item["runs"]) for item in trial_metrics}
        if len(runs) != 1:
            raise ValueError(
                f"Category {category} has different run counts across trials."
            )
        run_count = runs.pop()
        strategy_metrics = {}
        for strategy, answer_key, trace_key in (
            ("no_repair", "baseline_answer_correct", "baseline_trace_valid"),
            ("verified_global_regeneration", "global_answer_correct", "global_trace_valid"),
            ("verified_local_repair", "local_answer_correct", "local_trace_valid"),
        ):
            strategy_metrics[strategy] = {
                "answer_accuracy": summarize_values(
                    [item[answer_key] / run_count for item in trial_metrics], True
                ),
                "trace_valid_rate": summarize_values(
                    [item[trace_key] / run_count for item in trial_metrics], True
                ),
            }
        output[category] = {
            "runs_per_trial": run_count,
            "strategy_metrics": strategy_metrics,
        }
    return output


def render_markdown(
    aggregate: dict[str, object],
    problem_set: str,
    trial_count: int,
) -> str:
    lines = [
        "# MathRepair Category Analysis",
        "",
        f"Problem set: `{problem_set}` | Trials: {trial_count}",
        "",
        "Values are mean answer accuracy and valid-trace rate across seeds.",
        "",
        "| Category | Runs/trial | No repair | Global regeneration | Local repair |",
        "|---|---:|---:|---:|---:|",
    ]
    for category, data in aggregate.items():
        cells = []
        for strategy in (
            "no_repair",
            "verified_global_regeneration",
            "verified_local_repair",
        ):
            metrics = data["strategy_metrics"][strategy]
            cells.append(
                f"{metric_text(metrics['answer_accuracy'], True)} answer; "
                f"{metric_text(metrics['trace_valid_rate'], True)} trace"
            )
        lines.append(
            f"| {category} | {data['runs_per_trial']} | "
            + " | ".join(cells)
            + " |"
        )
    lines.extend(
        [
            "",
            "Interpretation: values summarize seed variation; they are not "
            "problem-sampling confidence intervals.",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, default=DEFAULT_DIR)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--markdown", type=Path)
    args = parser.parse_args()
    trial_dirs = sorted(
        path
        for path in args.input_dir.glob("seed_*")
        if (path / "repair_report.json").exists()
        and (path / "matched_budget_report.json").exists()
    )
    if len(trial_dirs) < 2:
        raise SystemExit("Input directory must contain at least two trials.")
    trial_data = []
    for trial_dir in trial_dirs:
        with (trial_dir / "repair_report.json").open(encoding="utf-8") as file:
            repair = json.load(file)
        with (trial_dir / "matched_budget_report.json").open(encoding="utf-8") as file:
            matched = json.load(file)
        trial_data.append((int(repair["base_seed"]), repair, matched))
    aggregate = aggregate_category_metrics(trial_data)
    problem_set = str(trial_data[0][1].get("problem_set", ""))
    aggregate_report = args.input_dir / "aggregate_report.json"
    if aggregate_report.exists():
        with aggregate_report.open(encoding="utf-8") as file:
            aggregate_metadata = json.load(file)
        problem_set = str(
            aggregate_metadata.get("problem_set", problem_set or args.input_dir.name)
        )
    if not problem_set:
        problem_set = args.input_dir.name
    if args.output is None:
        args.output = args.input_dir / "category_report.json"
    if args.markdown is None:
        args.markdown = args.input_dir / "category_report.md"
    args.output.write_text(
        json.dumps(
            {
                "problem_set": problem_set,
                "trial_count": len(trial_data),
                "categories": aggregate,
            },
            indent=2,
            ensure_ascii=True,
        )
        + "\n",
        encoding="utf-8",
    )
    args.markdown.write_text(
        render_markdown(aggregate, problem_set, len(trial_data)),
        encoding="utf-8",
    )
    print(f"JSON: {args.output}")
    print(f"Markdown: {args.markdown}")


if __name__ == "__main__":
    main()
