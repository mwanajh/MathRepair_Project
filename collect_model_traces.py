"""Run a local model on a batch of equations and evaluate its traces."""

import argparse
from collections import Counter, defaultdict
import csv
from datetime import datetime, timezone
import json
from pathlib import Path
import socket
import time
from urllib import error as url_error

from mathrepair_demo import normalize_solution_set, parse_equation
from model_pipeline import (
    OllamaMathModel,
    append_jsonl_record,
    run_pipeline,
    select_model_answer_step,
    save_trace,
)
import sympy as sp


DEFAULT_PROBLEMS = Path(__file__).with_name("model_problems.csv")
DEFAULT_TRACES = Path(__file__).with_name("batch_model_traces.jsonl")
DEFAULT_REPORT = Path(__file__).with_name("natural_model_report.json")


def is_infrastructure_failure(error: BaseException) -> bool:
    """Return whether a failure is a transient timeout or connection error."""
    if isinstance(error, url_error.HTTPError):
        return False
    if isinstance(error, (TimeoutError, socket.timeout, ConnectionError)):
        return True
    if isinstance(error, url_error.URLError):
        reason = error.reason
        if isinstance(reason, BaseException):
            return is_infrastructure_failure(reason)
        message = str(reason).lower()
        return "timed out" in message or "connection" in message
    return False


def answers_match(expected_text: str, actual_text: str) -> bool:
    """Compare expected and actual one-variable answer equations symbolically."""
    try:
        expected = parse_equation(expected_text)
        actual = parse_equation(actual_text)
    except (ValueError, TypeError, SyntaxError):
        return expected_text.strip() == actual_text.strip()

    variables = (
        expected.lhs.free_symbols
        | expected.rhs.free_symbols
        | actual.lhs.free_symbols
        | actual.rhs.free_symbols
    )
    if len(variables) != 1:
        return expected_text.strip() == actual_text.strip()
    variable = variables.pop()
    expected_set = normalize_solution_set(
        sp.solveset(expected, variable, domain=sp.S.Reals)
    )
    actual_set = normalize_solution_set(
        sp.solveset(actual, variable, domain=sp.S.Reals)
    )
    return expected_set == actual_set


def answer_signature(problem_text: str, answer_text: str) -> str:
    """Return a stable symbolic signature for answer-consistency metrics."""
    try:
        problem = parse_equation(problem_text)
        answer = parse_equation(answer_text)
    except (ValueError, TypeError, SyntaxError):
        return answer_text.strip()
    variables = problem.lhs.free_symbols | problem.rhs.free_symbols
    if len(variables) != 1:
        return answer_text.strip()
    variable = next(iter(variables))
    solutions = sp.solveset(answer, variable, domain=sp.S.Reals)
    return str(normalize_solution_set(solutions))


def load_problems(path: Path, limit: int | None) -> list[dict[str, str]]:
    """Load and validate batch problems from CSV."""
    with path.open(encoding="utf-8", newline="") as file:
        rows = list(csv.DictReader(file))
    required = {"problem", "expected_answer", "category"}
    if not rows or not required.issubset(rows[0]):
        raise ValueError(
            "Problems CSV must contain problem, expected_answer, and category."
        )
    return rows[:limit] if limit is not None else rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default="qwen2-math:1.5b")
    parser.add_argument("--problems", type=Path, default=DEFAULT_PROBLEMS)
    parser.add_argument("--traces", type=Path, default=DEFAULT_TRACES)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--delay", type=float, default=0.0)
    parser.add_argument("--samples-per-problem", type=int, default=1)
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--model-repair-attempts", type=int, default=1)
    parser.add_argument(
        "--prompt-profile",
        choices=["default", "qwen2_math_json"],
        default="default",
        help="Opt-in model-specific output contract; default preserves primary protocol.",
    )
    parser.add_argument(
        "--infrastructure-retries",
        type=int,
        default=2,
        help="Retry timeout/connection failures without changing the model seed.",
    )
    parser.add_argument(
        "--append",
        action="store_true",
        help="Append to the trace file instead of starting a fresh batch.",
    )
    args = parser.parse_args()

    if args.limit is not None and args.limit < 1:
        parser.error("--limit must be at least 1.")
    if args.delay < 0:
        parser.error("--delay cannot be negative.")
    if args.samples_per_problem < 1:
        parser.error("--samples-per-problem must be at least 1.")
    if args.temperature < 0:
        parser.error("--temperature cannot be negative.")
    if args.model_repair_attempts < 0:
        parser.error("--model-repair-attempts cannot be negative.")
    if args.infrastructure_retries < 0:
        parser.error("--infrastructure-retries cannot be negative.")

    try:
        problems = load_problems(args.problems, args.limit)
    except (OSError, ValueError) as error:
        parser.error(str(error))

    results: list[dict[str, object]] = []
    if not args.append:
        args.traces.write_text("", encoding="utf-8")
    print(f"=== Natural Model Batch: {args.model} ===")
    total_runs = len(problems) * args.samples_per_problem
    print(
        f"Problems: {len(problems)}; samples/problem: "
        f"{args.samples_per_problem}; runs: {total_runs}"
    )
    print(f"Temperature: {args.temperature}; base seed: {args.seed}\n")
    print(f"Model repair attempts per detected error: {args.model_repair_attempts}\n")

    run_number = 0
    for problem_index, item in enumerate(problems):
        problem = item["problem"]
        for sample_index in range(args.samples_per_problem):
            run_number += 1
            run_seed = args.seed + problem_index * 1000 + sample_index
            print(
                f"[{run_number}/{total_runs}] {problem} "
                f"(sample={sample_index + 1}, seed={run_seed})"
            )
            started = time.perf_counter()
            labels = {
                "expected_answer": item["expected_answer"],
                "category": item["category"],
                "sample_index": str(sample_index + 1),
                "seed": str(run_seed),
                "temperature": str(args.temperature),
                "prompt_profile": args.prompt_profile,
            }
            infrastructure_retry_count = 0
            model_client = OllamaMathModel(
                args.model,
                seed=run_seed,
                temperature=args.temperature,
                prompt_profile=args.prompt_profile,
            )
            try:
                while True:
                    try:
                        result = run_pipeline(
                            problem,
                            model_client,
                            provider="ollama",
                            model_name=args.model,
                            model_repair_attempts=args.model_repair_attempts,
                        )
                        break
                    except Exception as error:
                        if (
                            not is_infrastructure_failure(error)
                            or infrastructure_retry_count
                            >= args.infrastructure_retries
                        ):
                            raise
                        infrastructure_retry_count += 1
                        print(
                            "  infrastructure failure; retrying with the "
                            f"same seed ({infrastructure_retry_count}/"
                            f"{args.infrastructure_retries}): {error}"
                        )
                        model_client = OllamaMathModel(
                            args.model,
                            seed=run_seed,
                            temperature=args.temperature,
                            prompt_profile=args.prompt_profile,
                        )
                model_answer_step = select_model_answer_step(problem, result.steps)
                save_trace(args.traces, result, labels=labels)
                answer_correct = answers_match(
                    item["expected_answer"], model_answer_step
                )
                model_repair_answer_step = ""
                if result.model_repair.accepted:
                    model_repair_answer_step = select_model_answer_step(
                        problem, result.model_repair.repaired_steps
                    )
                post_model_repair_answer_correct = (
                    answers_match(
                        item["expected_answer"], model_repair_answer_step
                    )
                    if model_repair_answer_step
                    else answer_correct
                )
                record = {
                    "problem": problem,
                    "category": item["category"],
                    "sample_index": sample_index + 1,
                    "seed": run_seed,
                    "temperature": args.temperature,
                    "prompt_profile": args.prompt_profile,
                    "expected_answer": item["expected_answer"],
                    "model_final_step": result.steps[-1],
                    "model_answer_step": model_answer_step,
                    "answer_signature": answer_signature(problem, model_answer_step),
                    "reference_answer": result.analysis.correct_answer,
                    "answer_correct": answer_correct,
                    "model_trace_valid": result.analysis.error_node_id is None,
                    "first_error_node": result.analysis.error_node_id,
                    "error_type": result.analysis.error_type,
                    "repair_action": result.decision.action.value,
                    "auto_repair_attempted": result.repair.attempted,
                    "auto_repair_success": result.repair.success,
                    "repaired_steps": result.repair.repaired_steps,
                    "model_repair_attempted": result.model_repair.attempted,
                    "model_repair_accepted": result.model_repair.accepted,
                    "model_repair_attempt_count": len(
                        result.model_repair.attempts
                    ),
                    "model_repaired_steps": result.model_repair.repaired_steps,
                    "model_repair_answer_step": model_repair_answer_step,
                    "post_model_repair_answer_correct": (
                        post_model_repair_answer_correct
                    ),
                    "post_model_repair_trace_valid": (
                        result.analysis.error_node_id is None
                        or result.model_repair.accepted
                    ),
                    "model_repair_attempts": [
                        {
                            "attempt_index": attempt.attempt_index,
                            "input_valid_prefix": attempt.input_valid_prefix,
                            "input_trigger_step": attempt.input_trigger_step,
                            "input_error_type": attempt.input_error_type,
                            "candidate_steps": attempt.candidate_steps,
                            "ignored_repeated_prefix": (
                                attempt.ignored_repeated_prefix
                            ),
                            "accepted_steps": attempt.accepted_steps,
                            "discarded_steps": attempt.discarded_steps,
                            "accepted": attempt.accepted,
                            "rejection_reason": attempt.rejection_reason,
                            "first_error_node": attempt.first_error_node,
                            "error_type": attempt.error_type,
                            "generation_metadata": attempt.generation_metadata,
                        }
                        for attempt in result.model_repair.attempts
                    ],
                    "step_count": len(result.steps),
                    "elapsed_seconds": round(time.perf_counter() - started, 3),
                    "generation_metadata": result.generation_metadata,
                    "infrastructure_retry_count": infrastructure_retry_count,
                    "status": "completed",
                }
                print(
                    f"  steps={len(result.steps)}, "
                    f"trace_valid={record['model_trace_valid']}, "
                    f"answer_correct={answer_correct}, "
                    f"model_repair_accepted={result.model_repair.accepted}"
                )
            except Exception as error:
                record = {
                    "problem": problem,
                    "category": item["category"],
                    "sample_index": sample_index + 1,
                    "seed": run_seed,
                    "temperature": args.temperature,
                    "prompt_profile": args.prompt_profile,
                    "expected_answer": item["expected_answer"],
                    "status": "failed",
                    "failure": str(error),
                    "infrastructure_retry_count": infrastructure_retry_count,
                    "elapsed_seconds": round(time.perf_counter() - started, 3),
                }
                append_jsonl_record(
                    args.traces,
                    {
                        "status": "failed",
                        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                        "problem": problem,
                        "provider": "ollama",
                        "model": args.model,
                        "raw_response": model_client.last_raw_response,
                        "generation_metadata": model_client.last_metadata,
                        "failure": str(error),
                        "labels": labels,
                    },
                )
                print(f"  FAILED: {error}")
            results.append(record)
            if args.delay:
                time.sleep(args.delay)

    completed = [item for item in results if item["status"] == "completed"]
    trace_valid = sum(bool(item["model_trace_valid"]) for item in completed)
    answer_correct = sum(bool(item["answer_correct"]) for item in completed)
    failures = len(results) - len(completed)
    attempted_repairs = [
        item for item in completed if item["auto_repair_attempted"]
    ]
    successful_repairs = sum(
        bool(item["auto_repair_success"]) for item in attempted_repairs
    )
    model_repair_runs = [
        item for item in completed if item["model_repair_attempted"]
    ]
    accepted_model_repairs = sum(
        bool(item["model_repair_accepted"]) for item in model_repair_runs
    )
    post_model_repair_correct = sum(
        bool(item["post_model_repair_answer_correct"])
        for item in completed
    )
    post_model_repair_trace_valid = sum(
        bool(item["post_model_repair_trace_valid"])
        for item in completed
    )
    model_repair_attempt_count = sum(
        int(item["model_repair_attempt_count"]) for item in model_repair_runs
    )
    model_repair_retry_count = sum(
        max(0, int(item["model_repair_attempt_count"]) - 1)
        for item in model_repair_runs
    )
    model_repair_eval_tokens = sum(
        int(attempt["generation_metadata"].get("eval_count", 0))
        for item in model_repair_runs
        for attempt in item["model_repair_attempts"]
    )
    model_repair_continuation_count = sum(
        attempt["input_error_type"] == "incomplete_solution"
        for item in model_repair_runs
        for attempt in item["model_repair_attempts"]
    )
    corrected_wrong_answers = sum(
        not bool(item["answer_correct"])
        and bool(item["post_model_repair_answer_correct"])
        for item in completed
    )
    repair_regressions = sum(
        bool(item["answer_correct"])
        and not bool(item["post_model_repair_answer_correct"])
        for item in completed
    )
    total_eval_tokens = sum(
        int(item["generation_metadata"].get("eval_count", 0))
        for item in completed
    )
    category_counts: dict[str, dict[str, int]] = defaultdict(
        lambda: {"total": 0, "completed": 0, "trace_valid": 0, "answer_correct": 0}
    )
    for item in results:
        category = str(item["category"])
        category_counts[category]["total"] += 1
        if item["status"] == "completed":
            category_counts[category]["completed"] += 1
            category_counts[category]["trace_valid"] += int(
                bool(item["model_trace_valid"])
            )
            category_counts[category]["answer_correct"] += int(
                bool(item["answer_correct"])
            )
    error_type_counts = Counter(
        str(item["error_type"])
        for item in completed
        if item.get("error_type")
    )
    problem_results: dict[str, dict[str, object]] = {}
    for problem in problems:
        name = problem["problem"]
        runs = [item for item in results if item["problem"] == name]
        problem_completed = [item for item in runs if item["status"] == "completed"]
        signatures = sorted(
            {str(item["answer_signature"]) for item in problem_completed}
        )
        problem_results[name] = {
            "run_count": len(runs),
            "completed_count": len(problem_completed),
            "trace_valid_count": sum(
                bool(item["model_trace_valid"]) for item in problem_completed
            ),
            "answer_correct_count": sum(
                bool(item["answer_correct"]) for item in problem_completed
            ),
            "unique_answer_count": len(signatures),
            "answer_signatures": signatures,
        }
    summary = {
        "model": args.model,
        "problem_count": len(problems),
        "samples_per_problem": args.samples_per_problem,
        "run_count": len(results),
        "temperature": args.temperature,
        "prompt_profile": args.prompt_profile,
        "base_seed": args.seed,
        "completed_count": len(completed),
        "failure_count": failures,
        "infrastructure_retry_count": sum(
            int(item.get("infrastructure_retry_count", 0)) for item in results
        ),
        "trace_valid_count": trace_valid,
        "trace_valid_rate": trace_valid / len(completed) if completed else 0.0,
        "answer_correct_count": answer_correct,
        "answer_accuracy": answer_correct / len(completed) if completed else 0.0,
        "repair_attempt_count": len(attempted_repairs),
        "repair_success_count": successful_repairs,
        "repair_success_rate": (
            successful_repairs / len(attempted_repairs)
            if attempted_repairs
            else 0.0
        ),
        "model_repair_run_count": len(model_repair_runs),
        "model_repair_attempt_count": model_repair_attempt_count,
        "model_repair_retry_count": model_repair_retry_count,
        "model_repair_accept_count": accepted_model_repairs,
        "model_repair_accept_rate": (
            accepted_model_repairs / len(model_repair_runs)
            if model_repair_runs
            else 0.0
        ),
        "model_repair_eval_tokens": model_repair_eval_tokens,
        "model_repair_continuation_count": (
            model_repair_continuation_count
        ),
        "post_model_repair_answer_correct_count": post_model_repair_correct,
        "post_model_repair_answer_accuracy": (
            post_model_repair_correct / len(completed) if completed else 0.0
        ),
        "post_model_repair_trace_valid_count": post_model_repair_trace_valid,
        "post_model_repair_trace_valid_rate": (
            post_model_repair_trace_valid / len(completed)
            if completed
            else 0.0
        ),
        "model_repair_corrected_wrong_answer_count": corrected_wrong_answers,
        "model_repair_regression_count": repair_regressions,
        "total_eval_tokens": total_eval_tokens,
        "category_results": dict(category_counts),
        "error_type_counts": dict(error_type_counts),
        "problem_results": problem_results,
        "results": results,
    }
    with args.report.open("w", encoding="utf-8") as file:
        json.dump(summary, file, indent=2, ensure_ascii=True)

    print("\n--- Summary ---")
    print(f"Completed: {len(completed)}/{len(results)}")
    print(f"Trace valid: {trace_valid}/{len(completed)}")
    print(f"Answer correct: {answer_correct}/{len(completed)}")
    print(
        f"Automatic repairs: {successful_repairs}/"
        f"{len(attempted_repairs)} successful"
    )
    print(
        f"Model repairs accepted: {accepted_model_repairs}/"
        f"{len(model_repair_runs)} detected-error runs "
        f"({model_repair_attempt_count} candidate calls)"
    )
    print(
        f"Answer correct after model repair: {post_model_repair_correct}/"
        f"{len(completed)}"
    )
    print(
        f"Trace valid after model repair: {post_model_repair_trace_valid}/"
        f"{len(completed)}"
    )
    print(f"Total generated tokens: {total_eval_tokens}")
    print(f"Model repair tokens: {model_repair_eval_tokens}")
    print(f"Model repair retries: {model_repair_retry_count}")
    print(f"Continuation repair calls: {model_repair_continuation_count}")
    print(f"Wrong answers corrected: {corrected_wrong_answers}")
    print(f"Repair regressions: {repair_regressions}")
    consistent = sum(
        details["unique_answer_count"] == 1
        for details in problem_results.values()
        if details["completed_count"]
    )
    print(f"Answer-consistent problems: {consistent}/{len(problem_results)}")
    print("\n--- By category ---")
    for category, counts in sorted(category_counts.items()):
        print(
            f"{category}: completed={counts['completed']}/{counts['total']}, "
            f"trace_valid={counts['trace_valid']}, "
            f"answer_correct={counts['answer_correct']}"
        )
    if error_type_counts:
        print(f"Detected error types: {dict(error_type_counts)}")
    print(f"Report: {args.report}")
    print(f"Traces: {args.traces}")


if __name__ == "__main__":
    main()
