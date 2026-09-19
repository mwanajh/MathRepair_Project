"""Run and aggregate repeated MathRepair experiments across base seeds."""

import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import re
import shutil
import statistics
import subprocess
import sys

from collect_model_traces import answers_match, load_problems
from ollama_status import fetch_models


PROJECT_DIR = Path(__file__).resolve().parent
DEFAULT_PROBLEMS = PROJECT_DIR / "stress_model_problems.csv"
DEFAULT_OUTPUT_DIR = PROJECT_DIR / "repeated_experiments"
DEFAULT_SEEDS = [500, 20500, 40500, 60500, 80500]
T_CRITICAL_95 = {
    1: 12.706,
    2: 4.303,
    3: 3.182,
    4: 2.776,
    5: 2.571,
    6: 2.447,
    7: 2.365,
    8: 2.306,
    9: 2.262,
    10: 2.228,
    11: 2.201,
    12: 2.179,
    13: 2.160,
    14: 2.145,
    15: 2.131,
    16: 2.120,
    17: 2.110,
    18: 2.101,
    19: 2.093,
    20: 2.086,
    25: 2.060,
    30: 2.042,
}


def t_critical_95(degrees_of_freedom: int) -> float:
    """Return a conservative two-sided 95% Student-t critical value."""
    if degrees_of_freedom in T_CRITICAL_95:
        return T_CRITICAL_95[degrees_of_freedom]
    lower_keys = [key for key in T_CRITICAL_95 if key <= degrees_of_freedom]
    if lower_keys:
        return T_CRITICAL_95[max(lower_keys)]
    return 1.96


def summarize_values(values: list[float], bounded_rate: bool) -> dict[str, object]:
    """Calculate mean, sample SD, and a two-sided 95% Student-t interval."""
    if not values:
        raise ValueError("Metric values haziwezi kuwa tupu.")
    mean = statistics.fmean(values)
    standard_deviation = statistics.stdev(values) if len(values) > 1 else 0.0
    if len(values) > 1:
        margin = (
            t_critical_95(len(values) - 1)
            * standard_deviation
            / math.sqrt(len(values))
        )
    else:
        margin = 0.0
    lower = mean - margin
    upper = mean + margin
    if bounded_rate:
        lower = max(0.0, lower)
        upper = min(1.0, upper)
    return {
        "values": values,
        "mean": mean,
        "sample_standard_deviation": standard_deviation,
        "confidence_level": 0.95,
        "confidence_interval": [lower, upper],
        "trial_count": len(values),
    }


def validate_problem_set(path: Path) -> tuple[list[dict[str, str]], str]:
    """Load a problem set and verify its labels before model evaluation."""
    problems = load_problems(path, limit=None)
    duplicates = [
        problem
        for problem in {item["problem"] for item in problems}
        if sum(item["problem"] == problem for item in problems) > 1
    ]
    if duplicates:
        raise ValueError(f"Problem set contains a duplicate: {duplicates[0]}")
    invalid = [
        item["problem"]
        for item in problems
        if not answers_match(item["problem"], item["expected_answer"])
    ]
    if invalid:
        raise ValueError(
            "Expected answer is invalid for the problem: " + invalid[0]
        )
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return problems, digest


def model_slug(model: str) -> str:
    """Make an Ollama model name safe and readable in a folder name."""
    slug = re.sub(r"[^A-Za-z0-9._-]+", "_", model.strip()).strip("._-")
    return slug or "model"


def check_model_available(model: str) -> None:
    """Fail early if the requested model is not exposed by Ollama."""
    installed = {str(item.get("name", "")) for item in fetch_models()}
    if model not in installed:
        raise ValueError(
            f"Model is not installed in Ollama: {model}. "
            "Run python ollama_status.py to list available models."
        )


def aggregate_trial_reports(
    trials: list[dict[str, object]],
) -> dict[str, object]:
    """Aggregate matched-budget strategy metrics across independent base seeds."""
    if len(trials) < 2:
        raise ValueError("Repeated evaluation requires at least two trials.")
    model_names = {str(trial["model"]) for trial in trials}
    if len(model_names) != 1:
        raise ValueError(
            "Trial reports use different models; aggregation was stopped."
        )
    temperatures = {float(trial["temperature"]) for trial in trials}
    samples_per_problem = {
        int(trial["samples_per_problem"]) for trial in trials
    }
    if len(temperatures) != 1:
        raise ValueError(
            "Trial reports use different temperatures; aggregation "
            "was stopped."
        )
    prompt_profiles = {
        str(trial.get("prompt_profile", "default")) for trial in trials
    }
    if len(prompt_profiles) != 1:
        raise ValueError(
            "Trial reports use different prompt profiles; aggregation "
            "was stopped."
        )
    if len(samples_per_problem) != 1:
        raise ValueError(
            "Trial reports use different samples-per-problem values; aggregation "
            "was stopped."
        )
    problem_set_hashes = {str(trial["problem_set_sha256"]) for trial in trials}
    if len(problem_set_hashes) != 1:
        raise ValueError(
            "Trial reports use different problem sets; aggregation "
            "was stopped."
        )
    run_counts = [int(trial["run_count"]) for trial in trials]
    if any(run_count < 1 for run_count in run_counts):
        raise ValueError("Every trial must have a positive run_count.")
    if len(set(run_counts)) != 1:
        raise ValueError(
            "Trial reports have different run_count values; aggregation was stopped."
        )
    strategy_names = [item["name"] for item in trials[0]["strategies"]]
    strategy_metrics: dict[str, dict[str, object]] = {}
    for strategy_name in strategy_names:
        matching = [
            next(
                item
                for item in trial["strategies"]
                if item["name"] == strategy_name
            )
            for trial in trials
        ]
        strategy_metrics[strategy_name] = {
            "answer_accuracy": summarize_values(
                [float(item["answer_accuracy"]) for item in matching], True
            ),
            "trace_valid_rate": summarize_values(
                [float(item["trace_valid_rate"]) for item in matching], True
            ),
            "additional_model_calls": summarize_values(
                [float(item["additional_model_calls"]) for item in matching],
                False,
            ),
            "additional_tokens": summarize_values(
                [float(item["additional_tokens"]) for item in matching], False
            ),
        }

    local_name = "verified_local_repair"
    global_name = "verified_global_regeneration"
    answer_differences: list[float] = []
    trace_differences: list[float] = []
    for trial in trials:
        by_name = {item["name"]: item for item in trial["strategies"]}
        answer_differences.append(
            float(by_name[local_name]["answer_accuracy"])
            - float(by_name[global_name]["answer_accuracy"])
        )
        trace_differences.append(
            float(by_name[local_name]["trace_valid_rate"])
            - float(by_name[global_name]["trace_valid_rate"])
        )

    answer_difference = summarize_values(answer_differences, False)
    trace_difference = summarize_values(trace_differences, False)
    return {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "model": trials[0]["model"],
        "temperature": trials[0]["temperature"],
        "samples_per_problem": trials[0]["samples_per_problem"],
        "prompt_profile": trials[0].get("prompt_profile", "default"),
        "trial_count": len(trials),
        "runs_per_trial": run_counts[0],
        "problem_set": trials[0]["problem_set"],
        "problem_count": trials[0]["problem_count"],
        "problem_set_sha256": trials[0]["problem_set_sha256"],
        "base_seeds": [int(trial["base_seed"]) for trial in trials],
        "strategy_metrics": strategy_metrics,
        "paired_local_minus_global": {
            "answer_accuracy_difference": answer_difference,
            "trace_validity_difference": trace_difference,
            "answer_advantage_excludes_zero_95": (
                answer_difference["confidence_interval"][0] > 0
            ),
            "trace_advantage_excludes_zero_95": (
                trace_difference["confidence_interval"][0] > 0
            ),
        },
        "all_budget_comparisons_valid": all(
            bool(trial["matched_budget_comparison_valid"]) for trial in trials
        ),
        "trial_summaries": trials,
        "caveats": [
            (
                f"{len(trials)} trials provide only a preliminary variance "
                "estimate."
            ),
            (
                "Student-t intervals use "
                f"{len(trials) - 1} degrees of freedom."
            ),
            (
                f"The evaluation set has {trials[0]['problem_count']} problems "
                "and is not a benchmark."
            ),
            (
                "Trials reuse the same problems, so intervals reflect seed "
                "variation rather than problem-sampling uncertainty."
            ),
            "GPU sampling may vary even when base seeds are recorded.",
            "The problem-set hash is recorded to prevent cross-set aggregation.",
        ],
    }


def percent(value: float) -> str:
    return f"{100 * value:.1f}%"


def metric_text(metric: dict[str, object], percentage: bool) -> str:
    mean = float(metric["mean"])
    standard_deviation = float(metric["sample_standard_deviation"])
    lower, upper = metric["confidence_interval"]
    if percentage:
        return (
            f"{percent(mean)} +/- {percent(standard_deviation)} "
            f"[{percent(float(lower))}, {percent(float(upper))}]"
        )
    return (
        f"{mean:.1f} +/- {standard_deviation:.1f} "
        f"[{float(lower):.1f}, {float(upper):.1f}]"
    )


def render_markdown(summary: dict[str, object]) -> str:
    lines = [
        "# Repeated-Seed MathRepair Evaluation",
        "",
        (
            f"Trials: {summary['trial_count']} | Base seeds: "
            f"{', '.join(str(seed) for seed in summary['base_seeds'])}"
        ),
        f"Model: `{summary['model']}`",
        f"Prompt profile: `{summary.get('prompt_profile', 'default')}`",
        (
            f"Temperature: `{summary['temperature']}` | Samples/problem: "
            f"`{summary['samples_per_problem']}`"
        ),
        f"Problem set: `{summary['problem_set']}` ({summary['problem_count']} problems)",
        "",
        "Values are mean +/- sample SD with a 95% Student-t interval.",
        "",
        "| Strategy | Answer accuracy | Valid traces | Extra calls | Extra tokens |",
        "|---|---:|---:|---:|---:|",
    ]
    for name, metrics in summary["strategy_metrics"].items():
        lines.append(
            f"| {name} | {metric_text(metrics['answer_accuracy'], True)} | "
            f"{metric_text(metrics['trace_valid_rate'], True)} | "
            f"{metric_text(metrics['additional_model_calls'], False)} | "
            f"{metric_text(metrics['additional_tokens'], False)} |"
        )
    paired = summary["paired_local_minus_global"]
    lines.extend(
        [
            "",
            "## Paired Local Minus Global",
            "",
            "| Metric | Mean +/- SD [95% CI] |",
            "|---|---:|",
            (
                "| Answer accuracy difference | "
                f"{metric_text(paired['answer_accuracy_difference'], True)} |"
            ),
            (
                "| Trace-validity difference | "
                f"{metric_text(paired['trace_validity_difference'], True)} |"
            ),
            "",
            (
                "Answer advantage excludes zero at 95%: "
                f"**{paired['answer_advantage_excludes_zero_95']}**"
            ),
            (
                "Trace advantage excludes zero at 95%: "
                f"**{paired['trace_advantage_excludes_zero_95']}**"
            ),
            "",
            (
                "All matched-budget comparisons valid: "
                f"**{summary['all_budget_comparisons_valid']}**"
            ),
            "",
            "## Caveats",
            "",
        ]
    )
    lines.extend(f"- {item}" for item in summary["caveats"])
    return "\n".join(lines) + "\n"


def trial_summary(
    base_seed: int,
    repair_report: dict[str, object],
    matched_report: dict[str, object],
    expected_run_count: int,
    problem_set: str,
    problem_count: int,
    problem_set_sha256: str,
    expected_problems: list[str],
    expected_model: str,
    expected_temperature: float,
    expected_samples_per_problem: int,
    expected_prompt_profile: str = "default",
) -> dict[str, object]:
    report_model = str(repair_report.get("model", ""))
    matched_model = str(matched_report.get("source", {}).get("model", ""))
    if report_model != expected_model or matched_model != expected_model:
        raise ValueError(
            f"Seed {base_seed}: model report mismatch; expected {expected_model}."
        )
    report_temperature = float(repair_report.get("temperature", float("nan")))
    report_samples = int(repair_report.get("samples_per_problem", -1))
    if report_temperature != expected_temperature:
        raise ValueError(
            f"Seed {base_seed}: temperature report mismatch; expected "
            f"{expected_temperature}."
        )
    if report_samples != expected_samples_per_problem:
        raise ValueError(
            f"Seed {base_seed}: samples-per-problem report mismatch; expected "
            f"{expected_samples_per_problem}."
        )
    report_prompt_profile = str(repair_report.get("prompt_profile", "default"))
    if report_prompt_profile != expected_prompt_profile:
        raise ValueError(
            f"Seed {base_seed}: prompt profile mismatch; expected "
            f"{expected_prompt_profile}."
        )
    planned_runs = int(repair_report.get("run_count", -1))
    completed_runs = int(repair_report.get("completed_count", -1))
    matched_runs = int(matched_report.get("source", {}).get("run_count", -1))
    if planned_runs != expected_run_count:
        raise ValueError(
            f"Seed {base_seed}: expected {expected_run_count} planned runs, "
            f"report contains {planned_runs}."
        )
    if completed_runs != expected_run_count:
        failure_runs = int(repair_report.get("failure_count", 0))
        if completed_runs + failure_runs != expected_run_count:
            raise ValueError(
                f"Seed {base_seed}: completed {completed_runs} + failures "
                f"{failure_runs} != {expected_run_count}; trial "
                "an incomplete trial cannot be aggregated."
            )
    if matched_runs != expected_run_count:
        raise ValueError(
            f"Seed {base_seed}: matched report contains {matched_runs} runs, "
            f"expected {expected_run_count}."
        )
    report_problems = set(repair_report.get("problem_results", {}))
    if report_problems != set(expected_problems):
        raise ValueError(
            f"Seed {base_seed}: repair report uses a different problem set."
        )
    return {
        "base_seed": base_seed,
        "model": expected_model,
        "temperature": expected_temperature,
        "samples_per_problem": expected_samples_per_problem,
        "prompt_profile": expected_prompt_profile,
        "run_count": expected_run_count,
        "completed_count": completed_runs,
        "failure_count": int(repair_report.get("failure_count", 0)),
        "problem_set": problem_set,
        "problem_count": problem_count,
        "problem_set_sha256": problem_set_sha256,
        "matched_budget_comparison_valid": matched_report[
            "matched_budget_comparison_valid"
        ],
        "global_budget_utilization_rate": matched_report[
            "global_budget_utilization_rate"
        ],
        "strategies": matched_report["strategies"],
    }


def run_command(arguments: list[str]) -> None:
    subprocess.run(arguments, cwd=PROJECT_DIR, check=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seeds", type=int, nargs="+", default=DEFAULT_SEEDS)
    parser.add_argument("--problems", type=Path, default=DEFAULT_PROBLEMS)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--reuse-current-seed", type=int, default=500)
    parser.add_argument("--model", default="qwen2-math:1.5b")
    parser.add_argument("--temperature", type=float, default=1.4)
    parser.add_argument("--samples-per-problem", type=int, default=3)
    parser.add_argument("--model-repair-attempts", type=int, default=2)
    parser.add_argument(
        "--prompt-profile",
        choices=["default", "qwen2_math_json"],
        default="default",
        help="Opt-in model-specific output contract; default preserves primary protocol.",
    )
    parser.add_argument(
        "--skip-model-check",
        action="store_true",
        help="Skip Ollama preflight check; useful only for offline report tooling.",
    )
    parser.add_argument(
        "--aggregate-only",
        action="store_true",
        help="Rebuild aggregate tables from completed trial reports.",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Reuse completed trial reports and run only missing seeds.",
    )
    args = parser.parse_args()

    if len(set(args.seeds)) != len(args.seeds):
        parser.error("--seeds cannot contain duplicates.")
    if len(args.seeds) < 2:
        parser.error("Use at least two seeds for repeated evaluation.")
    if args.samples_per_problem < 1:
        parser.error("--samples-per-problem must be at least 1.")

    if not args.aggregate_only and not args.skip_model_check:
        try:
            check_model_available(args.model)
        except (RuntimeError, ValueError) as error:
            parser.error(str(error))

    problems_path = args.problems.resolve()
    try:
        problems, problem_set_sha256 = validate_problem_set(problems_path)
    except (OSError, ValueError) as error:
        parser.error(str(error))
    problem_count = len(problems)
    expected_run_count = problem_count * args.samples_per_problem
    if args.output_dir is None:
        model_suffix = ""
        if args.model != "qwen2-math:1.5b":
            model_suffix = f"_{model_slug(args.model)}"
        args.output_dir = (
            DEFAULT_OUTPUT_DIR if problems_path == DEFAULT_PROBLEMS.resolve()
            else PROJECT_DIR / f"{problems_path.stem}_repeated_experiments"
        )
        if model_suffix:
            args.output_dir = args.output_dir.with_name(
                args.output_dir.name + model_suffix
            )
    args.output_dir.mkdir(parents=True, exist_ok=True)
    trial_summaries: list[dict[str, object]] = []
    for trial_index, seed in enumerate(args.seeds, start=1):
        trial_dir = args.output_dir / f"seed_{seed}"
        trial_dir.mkdir(parents=True, exist_ok=True)
        repair_report = trial_dir / "repair_report.json"
        traces = trial_dir / "traces.jsonl"
        matched_report = trial_dir / "matched_budget_report.json"
        matched_markdown = trial_dir / "matched_budget_report.md"
        print(f"\n=== Trial {trial_index}/{len(args.seeds)}: seed {seed} ===")

        if args.aggregate_only:
            if not repair_report.exists() or not matched_report.exists():
                raise FileNotFoundError(
                    f"Completed repair/matched report is missing for seed {seed}."
                )
            print("Using completed trial report.")
        elif args.resume and repair_report.exists() and matched_report.exists():
            print("Resumed completed trial report.")
        elif (
            seed == args.reuse_current_seed
            and problems_path == DEFAULT_PROBLEMS.resolve()
            and args.prompt_profile == "default"
        ):
            current_report = PROJECT_DIR / "stress_multisample_report.json"
            current_traces = PROJECT_DIR / "stress_multisample_traces.jsonl"
            current_matched = PROJECT_DIR / "matched_budget_report.json"
            if not current_report.exists() or not current_matched.exists():
                raise FileNotFoundError(
                    "Current reports are missing for --reuse-current-seed."
                )
            with current_report.open(encoding="utf-8") as file:
                current_data = json.load(file)
            if int(current_data.get("base_seed", -1)) != seed:
                raise ValueError("Current report base_seed does not match the reuse seed.")
            shutil.copyfile(current_report, repair_report)
            shutil.copyfile(current_traces, traces)
            shutil.copyfile(current_matched, matched_report)
            if (PROJECT_DIR / "matched_budget_report.md").exists():
                shutil.copyfile(
                    PROJECT_DIR / "matched_budget_report.md", matched_markdown
                )
            print("Reused current seed report.")
        else:
            run_command(
                [
                    sys.executable,
                    "collect_model_traces.py",
                    "--model",
                    args.model,
                    "--problems",
                    str(problems_path),
                    "--samples-per-problem",
                    str(args.samples_per_problem),
                    "--temperature",
                    str(args.temperature),
                    "--seed",
                    str(seed),
                    "--model-repair-attempts",
                    str(args.model_repair_attempts),
                    "--prompt-profile",
                    args.prompt_profile,
                    "--traces",
                    str(traces),
                    "--report",
                    str(repair_report),
                ]
            )
            run_command(
                [
                    sys.executable,
                    "matched_budget_experiment.py",
                    "--input",
                    str(repair_report),
                    "--output",
                    str(matched_report),
                    "--markdown",
                    str(matched_markdown),
                ]
            )

        with matched_report.open(encoding="utf-8") as file:
            matched_data = json.load(file)
        with repair_report.open(encoding="utf-8") as file:
            repair_data = json.load(file)
        trial_summaries.append(
            trial_summary(
                seed,
                repair_data,
                matched_data,
                expected_run_count,
                problems_path.name,
                problem_count,
                problem_set_sha256,
                [item["problem"] for item in problems],
                args.model,
                args.temperature,
                args.samples_per_problem,
                args.prompt_profile,
            )
        )

    aggregate = aggregate_trial_reports(trial_summaries)
    aggregate_json = args.output_dir / "aggregate_report.json"
    aggregate_markdown = args.output_dir / "aggregate_report.md"
    aggregate_json.write_text(
        json.dumps(aggregate, indent=2, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )
    aggregate_markdown.write_text(render_markdown(aggregate), encoding="utf-8")
    print("\n=== Repeated-Seed Summary ===")
    for name, metrics in aggregate["strategy_metrics"].items():
        print(
            f"{name}: answer={percent(metrics['answer_accuracy']['mean'])}, "
            f"trace={percent(metrics['trace_valid_rate']['mean'])}"
        )
    print(f"JSON: {aggregate_json}")
    print(f"Markdown: {aggregate_markdown}")


if __name__ == "__main__":
    main()
