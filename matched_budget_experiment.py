"""Compare local repair with verified global regeneration under matched budgets."""

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import time
from typing import Callable

from collect_model_traces import answers_match
from model_pipeline import OllamaMathModel, select_model_answer_step
from model_repair import has_isolated_answer, trim_repeated_parent
from reasoning_chain import analyze_chain


DEFAULT_INPUT = Path(__file__).with_name("stress_multisample_report.json")
DEFAULT_OUTPUT = Path(__file__).with_name("matched_budget_report.json")
DEFAULT_MARKDOWN = Path(__file__).with_name("matched_budget_report.md")


def safe_rate(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 0.0


def repair_token_budget(record: dict[str, object]) -> int:
    """Return prompt plus completion tokens used by local repair for one run."""
    return sum(
        int(attempt.get("generation_metadata", {}).get("prompt_eval_count", 0))
        + int(attempt.get("generation_metadata", {}).get("eval_count", 0))
        for attempt in record.get("model_repair_attempts", [])
    )


def generation_token_budget(record: dict[str, object]) -> int:
    """Return baseline model-generation prompt plus completion tokens."""
    metadata = record.get("generation_metadata", {})
    return int(metadata.get("prompt_eval_count", 0)) + int(
        metadata.get("eval_count", 0)
    )


def attempt_token_budget(attempt: dict[str, object]) -> int:
    """Return prompt plus completion tokens for one recorded repair call."""
    metadata = attempt.get("generation_metadata", {})
    return int(metadata.get("prompt_eval_count", 0)) + int(
        metadata.get("eval_count", 0)
    )


def adaptive_risk_score(record: dict[str, object]) -> float:
    """Estimate local-repair risk from trace depth and typed error class."""
    step_count = max(1, int(record.get("step_count", 1)))
    error_node = str(record.get("first_error_node") or "n1")
    try:
        error_position = max(1, int(error_node.lstrip("n")))
    except ValueError:
        error_position = 1
    downstream = max(0, step_count - error_position + 1)
    error_weight = {
        "algebraic_transformation_error": 1.25,
        "logical_inference_error": 1.25,
        "dependency_error": 1.20,
        "missing_assumption": 1.15,
        "semantic_interpretation_error": 1.15,
        "sign_error": 1.05,
        "arithmetic_error": 1.00,
        "incomplete_solution": 1.00,
    }.get(str(record.get("error_type", "")), 1.00)
    return error_weight * (1.0 + downstream)


def allocate_integer_budget(total: int, weights: list[float]) -> list[int]:
    """Allocate an integer token ceiling with a largest-remainder rule."""
    if total < 0:
        raise ValueError("Budget cannot be negative.")
    if not weights:
        return []
    weight_total = sum(weights)
    if weight_total <= 0:
        return [0] * len(weights)
    exact = [total * weight / weight_total for weight in weights]
    allocation = [int(value) for value in exact]
    remaining = total - sum(allocation)
    ranked = sorted(
        range(len(weights)),
        key=lambda index: (exact[index] - allocation[index], -index),
        reverse=True,
    )
    for index in ranked[:remaining]:
        allocation[index] += 1
    return allocation


def replay_local_strategy(
    completed: list[dict[str, object]],
    error_runs: list[dict[str, object]],
    token_caps: list[int],
    name: str,
    baseline_answer_correct: int,
    baseline_trace_valid: int,
    baseline_calls: int,
    baseline_tokens: int,
    total_runs: int,
) -> dict[str, object]:
    """Replay recorded local candidates under a new per-run budget ceiling.

    This is a deterministic budget audit: it never treats a candidate that
    exceeded its assigned ceiling as accepted. A future live experiment can
    replace this replay with fresh model calls while keeping the same schema.
    """
    if len(error_runs) != len(token_caps):
        raise ValueError("Each error run needs exactly one local token cap.")

    additional_calls = 0
    additional_tokens = 0
    accepted_repairs = 0
    answer_correct = baseline_answer_correct
    trace_valid = baseline_trace_valid
    records: list[dict[str, object]] = []
    for record, cap in zip(error_runs, token_caps):
        observed_tokens = repair_token_budget(record)
        used_tokens = 0
        calls = 0
        for attempt in record.get("model_repair_attempts", []):
            attempt_tokens = attempt_token_budget(attempt)
            if used_tokens + attempt_tokens > cap:
                break
            used_tokens += attempt_tokens
            calls += 1
        accepted = bool(record.get("model_repair_accepted", False)) and (
            observed_tokens <= cap
        )
        if accepted:
            accepted_repairs += 1
            answer_correct += int(
                bool(record.get("post_model_repair_answer_correct", False))
            ) - int(bool(record.get("answer_correct", False)))
            trace_valid += int(not bool(record.get("model_trace_valid", False)))
        additional_calls += calls
        additional_tokens += used_tokens
        records.append(
            {
                "seed": record.get("seed"),
                "problem": record.get("problem"),
                "allocated_token_cap": cap,
                "observed_token_budget": observed_tokens,
                "used_tokens": used_tokens,
                "attempt_count": calls,
                "accepted": accepted,
                "budget_respected": observed_tokens <= cap,
            }
        )

    allocated_budget = sum(token_caps)
    return {
        "name": name,
        "answer_correct": answer_correct,
        "answer_accuracy": safe_rate(answer_correct, total_runs),
        "trace_valid": trace_valid,
        "trace_valid_rate": safe_rate(trace_valid, total_runs),
        "accepted_repairs": accepted_repairs,
        "repair_success": accepted_repairs,
        "repair_success_rate": safe_rate(accepted_repairs, len(error_runs)),
        "additional_model_calls": additional_calls,
        "additional_tokens": additional_tokens,
        "allocated_additional_tokens": allocated_budget,
        "total_model_calls": baseline_calls + additional_calls,
        "total_tokens": baseline_tokens + additional_tokens,
        "average_model_calls": safe_rate(
            baseline_calls + additional_calls, total_runs
        ),
        "average_tokens": safe_rate(baseline_tokens + additional_tokens, total_runs),
        "total_compute_cost": baseline_tokens + additional_tokens,
        "budget_respected": all(
            bool(item["budget_respected"]) for item in records
        ),
        "budget_records": records,
    }


def run_live_local_strategy(
    error_runs: list[dict[str, object]],
    token_caps: list[int],
    name: str,
    baseline_answer_correct: int,
    baseline_trace_valid: int,
    baseline_calls: int,
    baseline_tokens: int,
    total_runs: int,
    model_factory: Callable[[dict[str, object], int, int], object],
) -> dict[str, object]:
    """Generate and verify fresh local repairs under assigned token ceilings."""
    additional_calls = 0
    additional_tokens = 0
    accepted_repairs = 0
    answer_correct = baseline_answer_correct
    trace_valid = baseline_trace_valid
    budget_records: list[dict[str, object]] = []

    for record, cap in zip(error_runs, token_caps):
        prior_attempts = list(record.get("model_repair_attempts", []))
        if prior_attempts:
            template = prior_attempts[0]
            valid_prefix = list(template.get("input_valid_prefix", []))
            trigger_step = str(template.get("input_trigger_step", ""))
            error_type = str(
                template.get("input_error_type", record.get("error_type", ""))
            )
            expected_prompt_tokens = int(
                template.get("generation_metadata", {}).get(
                    "prompt_eval_count", 0
                )
            )
        else:
            valid_prefix = []
            trigger_step = str(record.get("model_final_step", ""))
            error_type = str(record.get("error_type", ""))
            expected_prompt_tokens = int(
                record.get("generation_metadata", {}).get(
                    "prompt_eval_count", 0
                )
            )

        used_tokens = 0
        attempts: list[dict[str, object]] = []
        accepted = False
        accepted_answer_correct = False
        while (
            not accepted
            and len(attempts) < 10
            and used_tokens + expected_prompt_tokens < cap
        ):
            attempt_index = len(attempts) + 1
            completion_cap = cap - used_tokens - expected_prompt_tokens
            model = model_factory(record, completion_cap, attempt_index)
            started = time.perf_counter()
            candidate_steps: list[str] = []
            try:
                candidate_steps = model.repair(
                    str(record["problem"]),
                    valid_prefix,
                    trigger_step,
                    error_type,
                    attempt_index,
                )
                candidate_suffix, ignored_prefix = trim_repeated_parent(
                    str(record["problem"]), valid_prefix, candidate_steps
                )
                repaired_steps = valid_prefix + candidate_suffix
                validation = analyze_chain(str(record["problem"]), repaired_steps)
                isolated_answer = has_isolated_answer(
                    str(record["problem"]), candidate_suffix
                )
                answer_step = select_model_answer_step(
                    str(record["problem"]), repaired_steps
                )
                candidate_answer_correct = answers_match(
                    str(record["expected_answer"]), answer_step
                )
                status = "completed"
                failure = ""
            except Exception as error:
                candidate_suffix = []
                ignored_prefix = []
                repaired_steps = []
                validation = None
                isolated_answer = False
                answer_step = ""
                candidate_answer_correct = False
                status = "failed"
                failure = str(error)

            metadata = dict(getattr(model, "last_repair_metadata", {}))
            actual_tokens = int(metadata.get("prompt_eval_count", 0)) + int(
                metadata.get("eval_count", 0)
            )
            within_budget = used_tokens + actual_tokens <= cap
            used_tokens += actual_tokens
            accepted = bool(
                within_budget
                and validation is not None
                and validation.error_node_id is None
                and isolated_answer
            )
            accepted_answer_correct = candidate_answer_correct if accepted else False
            attempts.append(
                {
                    "attempt_index": attempt_index,
                    "status": status,
                    "candidate_steps": candidate_steps,
                    "ignored_repeated_prefix": ignored_prefix,
                    "repaired_steps": repaired_steps,
                    "accepted": accepted,
                    "candidate_trace_valid": bool(
                        validation is not None
                        and validation.error_node_id is None
                    ),
                    "candidate_answer_correct": candidate_answer_correct,
                    "failure": failure,
                    "completion_token_cap": completion_cap,
                    "generation_tokens": metadata,
                    "total_tokens": actual_tokens,
                    "budget_respected": within_budget,
                    "elapsed_seconds": round(time.perf_counter() - started, 3),
                }
            )
            if actual_tokens == 0 or not within_budget:
                break

        if accepted:
            accepted_repairs += 1
            answer_correct += int(accepted_answer_correct) - int(
                bool(record.get("answer_correct", False))
            )
            trace_valid += 1
        additional_calls += len(attempts)
        additional_tokens += min(used_tokens, cap)
        budget_records.append(
            {
                "seed": record.get("seed"),
                "problem": record.get("problem"),
                "allocated_token_cap": cap,
                "used_tokens": min(used_tokens, cap),
                "attempt_count": len(attempts),
                "accepted": accepted,
                "budget_respected": all(
                    bool(attempt["budget_respected"]) for attempt in attempts
                ),
                "attempts": attempts,
            }
        )

    return {
        "name": name,
        "answer_correct": answer_correct,
        "answer_accuracy": safe_rate(answer_correct, total_runs),
        "trace_valid": trace_valid,
        "trace_valid_rate": safe_rate(trace_valid, total_runs),
        "accepted_repairs": accepted_repairs,
        "repair_success": accepted_repairs,
        "repair_success_rate": safe_rate(accepted_repairs, len(error_runs)),
        "additional_model_calls": additional_calls,
        "additional_tokens": additional_tokens,
        "allocated_additional_tokens": sum(token_caps),
        "total_model_calls": baseline_calls + additional_calls,
        "total_tokens": baseline_tokens + additional_tokens,
        "average_model_calls": safe_rate(
            baseline_calls + additional_calls, total_runs
        ),
        "average_tokens": safe_rate(baseline_tokens + additional_tokens, total_runs),
        "total_compute_cost": baseline_tokens + additional_tokens,
        "budget_respected": all(
            bool(item["budget_respected"]) for item in budget_records
        ),
        "budget_records": budget_records,
    }


def default_model_factory(
    report: dict[str, object],
) -> Callable[[dict[str, object], int, int], object]:
    model_name = str(report["model"])

    def create(
        record: dict[str, object], completion_cap: int, attempt_index: int
    ) -> OllamaMathModel:
        return OllamaMathModel(
            model_name,
            seed=int(record["seed"]) + 300_000 + attempt_index,
            temperature=float(record["temperature"]),
            max_output_tokens=completion_cap,
        )

    return create


def default_local_model_factory(
    report: dict[str, object], seed_offset: int
) -> Callable[[dict[str, object], int, int], object]:
    """Create fresh local-repair clients for one experimental arm."""
    model_name = str(report["model"])

    def create(
        record: dict[str, object], completion_cap: int, attempt_index: int
    ) -> OllamaMathModel:
        return OllamaMathModel(
            model_name,
            seed=int(record["seed"]) + seed_offset + attempt_index,
            temperature=float(record["temperature"]),
            max_output_tokens=completion_cap,
            prompt_profile=str(report.get("prompt_profile", "default")),
        )

    return create


def run_matched_budget(
    report: dict[str, object],
    model_factory: Callable[[dict[str, object], int, int], object] | None = None,
    global_results_override: list[dict[str, object]] | None = None,
    live_local: bool = False,
    uniform_local_factory: Callable[
        [dict[str, object], int, int], object
    ] | None = None,
    adaptive_local_factory: Callable[
        [dict[str, object], int, int], object
    ] | None = None,
    local_strategies_override: list[dict[str, object]] | None = None,
    local_evaluation_mode_override: str | None = None,
) -> dict[str, object]:
    """Compare regeneration and local strategies under matched token ceilings.

    ``global_results_override`` supports a deterministic report rebuild from a
    previously measured global-regeneration run without making new model calls.
    """
    all_results = list(report.get("results", []))
    completed = [
        item
        for item in all_results
        if item.get("status") == "completed"
    ]
    failed = [item for item in all_results if item.get("status") != "completed"]
    if not completed:
        raise ValueError("Input report contains no completed results.")
    error_runs = [item for item in completed if not item["model_trace_valid"]]
    factory = model_factory or default_model_factory(report)

    global_results: list[dict[str, object]] = list(global_results_override or [])
    global_records_to_run = [] if global_results_override is not None else error_runs
    for run_number, record in enumerate(global_records_to_run, start=1):
        total_budget = repair_token_budget(record)
        expected_prompt_tokens = int(
            record.get("generation_metadata", {}).get("prompt_eval_count", 0)
        )
        print(
            f"[{run_number}/{len(error_runs)}] seed={record['seed']} "
            f"budget={total_budget}"
        )
        started = time.perf_counter()
        if total_budget - expected_prompt_tokens < 1:
            global_results.append(
                {
                    "seed": record["seed"],
                    "problem": record["problem"],
                    "category": record["category"],
                    "status": "skipped",
                    "accepted": False,
                    "failure": "Budget is insufficient after the global prompt cost.",
                    "local_repair_token_budget": total_budget,
                    "attempts": [],
                    "attempt_count": 0,
                    "global_total_tokens": 0,
                    "budget_respected": True,
                    "original_answer_correct": record["answer_correct"],
                    "post_global_answer_correct": record["answer_correct"],
                    "post_global_trace_valid": False,
                }
            )
            continue

        attempts: list[dict[str, object]] = []
        used_tokens = 0
        accepted = False
        accepted_answer_correct = False
        while (
            not accepted
            and len(attempts) < 10
            and used_tokens + expected_prompt_tokens < total_budget
        ):
            attempt_index = len(attempts) + 1
            completion_cap = (
                total_budget - used_tokens - expected_prompt_tokens
            )
            attempt_started = time.perf_counter()
            infrastructure_retries = 0
            generation_error: Exception | None = None
            while True:
                model = factory(record, completion_cap, attempt_index)
                try:
                    steps = model.solve(str(record["problem"]))
                    generation_error = None
                    break
                except Exception as error:
                    generation_error = error
                    failed_metadata = dict(
                        getattr(model, "last_metadata", {})
                    )
                    failed_tokens = int(
                        failed_metadata.get("prompt_eval_count", 0)
                    ) + int(failed_metadata.get("eval_count", 0))
                    if failed_tokens or infrastructure_retries >= 2:
                        break
                    infrastructure_retries += 1
                    print(
                        "  infrastructure retry "
                        f"{infrastructure_retries}/2: {error}"
                    )

            try:
                if generation_error is not None:
                    raise generation_error
                analysis = analyze_chain(str(record["problem"]), steps)
                isolated_answer = has_isolated_answer(
                    str(record["problem"]), steps
                )
                accepted = analysis.error_node_id is None and isolated_answer
                answer_step = select_model_answer_step(
                    str(record["problem"]), steps
                )
                candidate_answer_correct = answers_match(
                    str(record["expected_answer"]), answer_step
                )
                accepted_answer_correct = (
                    candidate_answer_correct if accepted else False
                )
                status = "completed"
                failure = ""
            except Exception as error:
                steps = []
                isolated_answer = False
                accepted = False
                answer_step = ""
                candidate_answer_correct = False
                analysis = None
                status = "failed"
                failure = str(error)

            metadata = dict(getattr(model, "last_metadata", {}))
            actual_tokens = int(metadata.get("prompt_eval_count", 0)) + int(
                metadata.get("eval_count", 0)
            )
            used_tokens += actual_tokens
            attempt = {
                "attempt_index": attempt_index,
                "global_seed": int(record["seed"]) + 300_000 + attempt_index,
                "status": status,
                "steps": steps,
                "accepted": accepted,
                "candidate_trace_valid": (
                    analysis.error_node_id is None if analysis else False
                ),
                "candidate_has_isolated_answer": isolated_answer,
                "candidate_answer_step": answer_step,
                "candidate_answer_correct": candidate_answer_correct,
                "first_error_node": (
                    analysis.error_node_id if analysis else None
                ),
                "error_type": analysis.error_type if analysis else "",
                "failure": failure,
                "infrastructure_retries": infrastructure_retries,
                "completion_token_cap": completion_cap,
                "generation_tokens": metadata,
                "total_tokens": actual_tokens,
                "elapsed_seconds": round(
                    time.perf_counter() - attempt_started, 3
                ),
            }
            attempts.append(attempt)
            print(
                f"  attempt={attempt_index}, accepted={accepted}, "
                f"tokens={actual_tokens}, used={used_tokens}/{total_budget}"
            )
            if actual_tokens == 0:
                break

        post_answer_correct = (
            accepted_answer_correct
            if accepted
            else bool(record["answer_correct"])
        )
        result = {
            "seed": record["seed"],
            "problem": record["problem"],
            "category": record["category"],
            "status": "completed" if attempts else "skipped",
            "attempts": attempts,
            "attempt_count": len(attempts),
            "accepted": accepted,
            "original_answer_correct": record["answer_correct"],
            "post_global_answer_correct": post_answer_correct,
            "post_global_trace_valid": accepted,
            "local_model_repair_accepted": record.get(
                "model_repair_accepted", False
            ),
            "local_post_answer_correct": record.get(
                "post_model_repair_answer_correct", record["answer_correct"]
            ),
            "local_repair_token_budget": total_budget,
            "global_total_tokens": used_tokens,
            "budget_respected": used_tokens <= total_budget,
            "elapsed_seconds": round(time.perf_counter() - started, 3),
        }
        global_results.append(result)

    # Failed model generations remain in the evaluation denominator. They
    # cannot receive a repair strategy, so they contribute zero successes.
    total_runs = len(all_results)
    baseline_answer_correct = sum(bool(item["answer_correct"]) for item in completed)
    baseline_trace_valid = sum(bool(item["model_trace_valid"]) for item in completed)
    local_answer_correct = sum(
        bool(item.get("post_model_repair_answer_correct", item["answer_correct"]))
        for item in completed
    )
    local_trace_valid = sum(
        bool(item["model_trace_valid"])
        or bool(item.get("model_repair_accepted", False))
        for item in completed
    )
    global_answer_correct = baseline_answer_correct - sum(
        bool(item["answer_correct"]) for item in error_runs
    ) + sum(bool(item["post_global_answer_correct"]) for item in global_results)
    global_trace_valid = baseline_trace_valid + sum(
        bool(item["post_global_trace_valid"]) for item in global_results
    )
    global_accepted = sum(bool(item["accepted"]) for item in global_results)
    global_call_count = sum(
        int(item.get("attempt_count", 0)) for item in global_results
    )
    local_budget = sum(repair_token_budget(item) for item in error_runs)
    global_tokens = sum(int(item.get("global_total_tokens", 0)) for item in global_results)
    baseline_calls = len(completed)
    baseline_tokens = sum(generation_token_budget(item) for item in completed)
    global_budget_violations = sum(
        not bool(item.get("budget_respected", False)) for item in global_results
    )

    uniform_cap = local_budget // len(error_runs) if error_runs else 0
    uniform_caps = [uniform_cap] * len(error_runs)
    adaptive_caps = allocate_integer_budget(
        local_budget, [adaptive_risk_score(item) for item in error_runs]
    )
    if local_strategies_override is not None:
        by_name = {
            str(item.get("name")): item for item in local_strategies_override
        }
        try:
            uniform_strategy = by_name["verified_local_repair_uniform"]
            adaptive_strategy = by_name["verified_local_repair_adaptive"]
        except KeyError as error:
            raise ValueError(
                "Local override is missing a uniform or adaptive strategy."
            ) from error
        local_evaluation_mode = local_evaluation_mode_override or "reused"
    elif live_local:
        uniform_factory = uniform_local_factory or default_local_model_factory(
            report, 400_000
        )
        adaptive_factory = adaptive_local_factory or default_local_model_factory(
            report, 500_000
        )
        uniform_strategy = run_live_local_strategy(
            error_runs,
            uniform_caps,
            "verified_local_repair_uniform",
            baseline_answer_correct,
            baseline_trace_valid,
            baseline_calls,
            baseline_tokens,
            total_runs,
            uniform_factory,
        )
        adaptive_strategy = run_live_local_strategy(
            error_runs,
            adaptive_caps,
            "verified_local_repair_adaptive",
            baseline_answer_correct,
            baseline_trace_valid,
            baseline_calls,
            baseline_tokens,
            total_runs,
            adaptive_factory,
        )
        local_evaluation_mode = "live"
    else:
        uniform_strategy = replay_local_strategy(
            completed,
            error_runs,
            uniform_caps,
            "verified_local_repair_uniform",
            baseline_answer_correct,
            baseline_trace_valid,
            baseline_calls,
            baseline_tokens,
            total_runs,
        )
        adaptive_strategy = replay_local_strategy(
            completed,
            error_runs,
            adaptive_caps,
            "verified_local_repair_adaptive",
            baseline_answer_correct,
            baseline_trace_valid,
            baseline_calls,
            baseline_tokens,
            total_runs,
        )
        local_evaluation_mode = "replay"

    global_strategy = {
        "name": "verified_global_regeneration",
        "answer_correct": global_answer_correct,
        "answer_accuracy": safe_rate(global_answer_correct, total_runs),
        "trace_valid": global_trace_valid,
        "trace_valid_rate": safe_rate(global_trace_valid, total_runs),
        "accepted_repairs": global_accepted,
        "repair_success": global_accepted,
        "repair_success_rate": safe_rate(global_accepted, len(error_runs)),
        "additional_model_calls": global_call_count,
        "additional_tokens": global_tokens,
        "allocated_additional_tokens": local_budget,
        "total_model_calls": baseline_calls + global_call_count,
        "total_tokens": baseline_tokens + global_tokens,
        "average_model_calls": safe_rate(
            baseline_calls + global_call_count, total_runs
        ),
        "average_tokens": safe_rate(baseline_tokens + global_tokens, total_runs),
        "total_compute_cost": baseline_tokens + global_tokens,
        "budget_respected": global_budget_violations == 0,
    }
    local_budget_violations = int(
        not bool(uniform_strategy.get("budget_respected", False))
    ) + int(not bool(adaptive_strategy.get("budget_respected", False)))
    budget_violations = global_budget_violations + local_budget_violations

    return {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "local_evaluation_mode": local_evaluation_mode,
        "source": {
            "model": report.get("model", ""),
            "run_count": total_runs,
            "completed_count": len(completed),
            "failure_count": len(failed),
            "detected_error_runs": len(error_runs),
            "temperature": report.get("temperature", 0.0),
        },
        "budget_definition": (
            "Each repair strategy receives approximately the same total "
            "additional prompt-plus-completion token ceiling across detected "
            "error runs. Global retains recorded per-run ceilings; uniform and "
            "adaptive local repair redistribute the shared total."
        ),
        "local_repair_additional_token_budget": local_budget,
        "global_regeneration_additional_tokens": global_tokens,
        "global_budget_utilization_rate": safe_rate(global_tokens, local_budget),
        "global_budget_violation_count": global_budget_violations,
        "local_budget_violation_count": local_budget_violations,
        "budget_violation_count": budget_violations,
        "matched_budget_comparison_valid": (
            budget_violations == 0
            and uniform_strategy["allocated_additional_tokens"] <= local_budget
            and adaptive_strategy["allocated_additional_tokens"] == local_budget
            and bool(uniform_strategy.get("budget_respected", False))
            and bool(adaptive_strategy.get("budget_respected", False))
        ),
        "compute_cost_definition": (
            "Total compute cost is reported as prompt-plus-completion token "
            "equivalents; dollar cost requires a model/provider price card."
        ),
        "matched_additional_token_budget": local_budget,
        "uniform_budget_per_error_run": uniform_cap,
        "adaptive_budget_allocation": adaptive_caps,
        "answer_accuracy_difference_vs_global_percentage_points": {
            "verified_local_repair_uniform": 100
            * (
                float(uniform_strategy["answer_accuracy"])
                - float(global_strategy["answer_accuracy"])
            ),
            "verified_local_repair_adaptive": 100
            * (
                float(adaptive_strategy["answer_accuracy"])
                - float(global_strategy["answer_accuracy"])
            ),
        },
        "strategies": [
            {
                "name": "no_repair",
                "answer_correct": baseline_answer_correct,
                "answer_accuracy": safe_rate(baseline_answer_correct, total_runs),
                "trace_valid": baseline_trace_valid,
                "trace_valid_rate": safe_rate(baseline_trace_valid, total_runs),
                "repair_success": 0,
                "repair_success_rate": 0.0,
                "additional_model_calls": 0,
                "additional_tokens": 0,
                "allocated_additional_tokens": 0,
                "total_model_calls": baseline_calls,
                "total_tokens": baseline_tokens,
                "average_model_calls": safe_rate(baseline_calls, total_runs),
                "average_tokens": safe_rate(baseline_tokens, total_runs),
                "total_compute_cost": baseline_tokens,
            },
            global_strategy,
            uniform_strategy,
            adaptive_strategy,
        ],
        "global_regeneration_results": global_results,
        "caveats": ([
            "This is a small stress set and not a benchmark result.",
            "Both repair strategies use the same symbolic verifier gate.",
            "Global regeneration retries only while its per-error budget remains.",
            (
                "Uniform and adaptive local strategies use fresh model calls."
                if local_evaluation_mode == "live"
                else "Uniform and adaptive local strategies replay recorded local candidates under their allocated ceilings; they do not make new model calls."
            ),
            "Adaptive local caps use trace depth and typed-error risk as a pre-registered heuristic.",
            "GPU sampling may vary slightly even with recorded seeds.",
        ] + (
            [
                "No invalid completed traces were detected, so neither repair "
                "strategy had an eligible run in this trial."
            ]
            if not error_runs
            else []
        )),
    }


def percent(value: float) -> str:
    return f"{100 * value:.1f}%"


def render_markdown(summary: dict[str, object]) -> str:
    source = summary["source"]
    lines = [
        "# Matched-Budget Repair Comparison",
        "",
        (
            f"Model: `{source['model']}` | Runs: {source['run_count']} | "
            f"Detected errors: {source['detected_error_runs']}"
        ),
        "",
        f"Budget rule: {summary['budget_definition']}",
        "",
        (
            "| Strategy | Answer accuracy | Valid traces | Repair success | "
            "Avg calls | Avg tokens | Total compute cost |"
        ),
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for strategy in summary["strategies"]:
        lines.append(
            f"| {strategy['name']} | {percent(strategy['answer_accuracy'])} "
            f"({strategy['answer_correct']}/{source['run_count']}) | "
            f"{percent(strategy['trace_valid_rate'])} "
            f"({strategy['trace_valid']}/{source['run_count']}) | "
            f"{percent(strategy.get('repair_success_rate', 0.0))} "
            f"({strategy.get('repair_success', 0)}/"
            f"{source['detected_error_runs']}) | "
            f"{strategy.get('average_model_calls', 0.0):.2f} | "
            f"{strategy.get('average_tokens', 0.0):.1f} | "
            f"{strategy.get('total_compute_cost', 0):,} tokens |"
        )
    lines.extend(
        [
            "",
            (
            "Global budget utilization: "
            f"{percent(summary['global_budget_utilization_rate'])}"
        ),
            (
                "Matched additional-token ceiling: "
                f"{summary['matched_additional_token_budget']:,}"
            ),
            (
                "Matched-budget comparison valid: "
                f"**{summary['matched_budget_comparison_valid']}**"
            ),
            (
                "Uniform local minus global answer accuracy: "
                f"{summary['answer_accuracy_difference_vs_global_percentage_points']['verified_local_repair_uniform']:+.1f} pp"
            ),
            (
                "Adaptive local minus global answer accuracy: "
                f"{summary['answer_accuracy_difference_vs_global_percentage_points']['verified_local_repair_adaptive']:+.1f} pp"
            ),
            "",
            "## Caveats",
            "",
        ]
    )
    lines.extend(f"- {item}" for item in summary["caveats"])
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--markdown", type=Path, default=DEFAULT_MARKDOWN)
    parser.add_argument(
        "--reuse-global-results",
        action="store_true",
        help="Rebuild metrics from the output file's saved global attempts.",
    )
    parser.add_argument(
        "--live-local",
        action="store_true",
        help="Generate fresh uniform/adaptive local repairs instead of replaying saved candidates.",
    )
    parser.add_argument(
        "--reuse-local-results",
        action="store_true",
        help="Rebuild metrics from the output file's saved uniform/adaptive arms.",
    )
    args = parser.parse_args()

    with args.input.open(encoding="utf-8") as file:
        report = json.load(file)
    global_results_override = None
    local_strategies_override = None
    local_evaluation_mode_override = None
    if args.reuse_global_results or args.reuse_local_results:
        if not args.output.exists():
            parser.error("Reuse options require an existing output file.")
        prior_summary = json.loads(args.output.read_text(encoding="utf-8"))
    if args.reuse_global_results:
        global_results_override = list(
            prior_summary.get("global_regeneration_results", [])
        )
        if not global_results_override and any(
            not item.get("model_trace_valid", False)
            for item in report.get("results", [])
            if item.get("status") == "completed"
        ):
            parser.error("Existing output has no reusable global results.")
    if args.reuse_local_results:
        local_strategies_override = [
            item
            for item in prior_summary.get("strategies", [])
            if item.get("name")
            in {
                "verified_local_repair_uniform",
                "verified_local_repair_adaptive",
            }
        ]
        if len(local_strategies_override) != 2:
            parser.error("Existing output has no reusable local strategy results.")
        local_evaluation_mode_override = str(
            prior_summary.get("local_evaluation_mode", "reused")
        )
    summary = run_matched_budget(
        report,
        global_results_override=global_results_override,
        live_local=args.live_local,
        local_strategies_override=local_strategies_override,
        local_evaluation_mode_override=local_evaluation_mode_override,
    )
    args.output.write_text(
        json.dumps(summary, indent=2, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )
    args.markdown.write_text(render_markdown(summary), encoding="utf-8")

    print("\n--- Matched-Budget Summary ---")
    for strategy in summary["strategies"]:
        print(
            f"{strategy['name']}: answer={percent(strategy['answer_accuracy'])}, "
            f"trace={percent(strategy['trace_valid_rate'])}, "
            f"repair={percent(strategy.get('repair_success_rate', 0.0))}, "
            f"avg_calls={strategy.get('average_model_calls', 0.0):.2f}, "
            f"avg_tokens={strategy.get('average_tokens', 0.0):.1f}, "
            f"cost={strategy.get('total_compute_cost', 0)}"
        )
    print(
        "Budget valid: "
        f"{summary['matched_budget_comparison_valid']} "
        f"(violations={summary['budget_violation_count']})"
    )
    print(f"JSON: {args.output}")
    print(f"Markdown: {args.markdown}")


if __name__ == "__main__":
    main()
