"""Run matched-budget system ablations from one frozen MATH-500 baseline."""

import argparse
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
import time
from typing import Callable

import joblib

from benchmark_pilot import load_pilot
from frozen_protocol import (
    FROZEN_BASE_SEED,
    FROZEN_MODEL,
    FROZEN_PROMPT_PROFILE,
    FROZEN_TEMPERATURE,
    ProtocolDrift,
    require_frozen_base,
)
from learned_verifier import (
    DEFAULT_DATASET,
    LearnedTypedVerifier,
    current_rule_baseline,
    load_examples,
    train_verifier,
)
from math500_evaluation import load_checkpoint, token_count, trace_nodes
from math_answer_scoring import answers_equivalent, extract_final_answer
from model_pipeline import OllamaMathModel, append_jsonl_record, parse_normalized_text_steps
from repair_acceptance import compare_repair_states
from rescore_math500 import load_trace_records


PROJECT_DIR = Path(__file__).resolve().parent
DEFAULT_PROBLEMS = PROJECT_DIR / "math500_pilot_40.json"
DEFAULT_BASELINE = PROJECT_DIR / "math500_full40_baseline_traces.jsonl"
DEFAULT_VERIFIER = PROJECT_DIR / "learned_verifier_model.joblib"
DEFAULT_REPORT = PROJECT_DIR / "math500_system_ablation_report.json"
VARIANTS = ("full_mathrepair", "no_graph", "no_typed_error", "no_symbolic_tool")


def predict_for_variant(
    variant: str,
    problem: str,
    steps: list[str],
    full_verifier: LearnedTypedVerifier,
    no_graph_verifier: LearnedTypedVerifier,
) -> tuple[dict[str, object], list[dict[str, object]]]:
    """Apply the exact component switches for one system variant."""
    graph_enabled = variant != "no_graph"
    nodes = trace_nodes(problem, steps, graph=graph_enabled)
    verifier = no_graph_verifier if variant == "no_graph" else full_verifier
    prediction = verifier.predict(problem, nodes)
    prediction["prediction_source"] = "learned_verifier"
    symbolic_enabled = variant != "no_symbolic_tool"
    if symbolic_enabled:
        symbolic = current_rule_baseline(
            {"problem": problem, "corrupted_trace": nodes}
        )
        if symbolic["error_location"] is not None:
            prediction.update(symbolic)
            prediction["location_confidence"] = 1.0
            prediction["prediction_source"] = "structural_symbolic_heuristic"
    if variant == "no_typed_error" and prediction["error_location"]:
        prediction["error_type"] = ""
    return prediction, nodes


def compact_arm_checkpoint(record: dict[str, object]) -> dict[str, object]:
    """Return fields used by arm aggregation from a raw checkpoint record."""
    keys = (
        "benchmark_id",
        "subject",
        "level",
        "status",
        "initial_answer",
        "initial_answer_correct",
        "predicted_error_location",
        "predicted_error_type",
        "prediction_source",
        "location_confidence",
        "repair_attempted",
        "repair_generation_succeeded",
        "repair_accepted",
        "repair_rejection_reason",
        "repair_success",
        "final_answer",
        "final_answer_correct",
        "repair_regression",
        "additional_model_calls",
        "additional_prompt_tokens",
        "additional_tokens",
        "budget_skipped",
        "elapsed_seconds",
        "failure",
    )
    return {key: record.get(key) for key in keys}


def summarize_arm(
    variant: str,
    results: list[dict[str, object]],
    problem_count: int,
    budget: int | None,
) -> dict[str, object]:
    completed = [item for item in results if item.get("status") == "completed"]
    attempted = [item for item in completed if item.get("repair_attempted")]
    additional_tokens = sum(int(item.get("additional_tokens") or 0) for item in results)
    additional_calls = sum(int(item.get("additional_model_calls") or 0) for item in results)
    return {
        "variant_id": variant,
        "problem_count": problem_count,
        "completed_baseline_count": len(completed),
        "baseline_failure_count": problem_count - len(completed),
        "initial_answer_accuracy": sum(
            bool(item.get("initial_answer_correct")) for item in completed
        )
        / problem_count,
        "final_answer_accuracy": sum(
            bool(item.get("final_answer_correct")) for item in completed
        )
        / problem_count,
        "verifier_detection_count": sum(
            bool(item.get("predicted_error_location")) for item in completed
        ),
        "prediction_source_counts": dict(
            Counter(str(item.get("prediction_source", "none")) for item in completed)
        ),
        "predicted_error_type_counts": dict(
            Counter(
                str(item.get("predicted_error_type") or "untyped")
                for item in completed
                if item.get("predicted_error_location")
            )
        ),
        "repair_attempt_count": len(attempted),
        "repair_generation_success_count": sum(
            bool(item.get("repair_generation_succeeded")) for item in attempted
        ),
        "repair_accepted_count": sum(bool(item.get("repair_accepted")) for item in attempted),
        "repair_gate_rejection_count": sum(
            bool(item.get("repair_generation_succeeded")) and not bool(item.get("repair_accepted"))
            for item in attempted
        ),
        "repair_success_count": sum(bool(item.get("repair_success")) for item in attempted),
        "repair_success_rate": (
            sum(bool(item.get("repair_success")) for item in attempted) / len(attempted)
            if attempted
            else 0.0
        ),
        "repair_regression_count": sum(
            bool(item.get("repair_regression")) for item in attempted
        ),
        "budget_skipped_count": sum(bool(item.get("budget_skipped")) for item in completed),
        "additional_model_calls": additional_calls,
        "additional_tokens": additional_tokens,
        "average_additional_tokens": additional_tokens / problem_count,
        "matched_additional_token_budget": budget,
        "budget_respected": budget is None or additional_tokens <= budget,
        "results": results,
    }


def run_arm(
    variant: str,
    problems: list[dict[str, object]],
    baseline_by_id: dict[str, dict[str, object]],
    full_verifier: LearnedTypedVerifier,
    no_graph_verifier: LearnedTypedVerifier,
    model_name: str,
    trace_path: Path,
    *,
    seed: int,
    temperature: float,
    timeout_seconds: int,
    max_output_tokens: int,
    budget: int | None,
    expected_prompt_tokens: dict[str, int] | None = None,
    per_problem_budgets: dict[str, int] | None = None,
    model_factory: Callable[[int, int], object] | None = None,
    resume: bool = False,
    prompt_profile: str = FROZEN_PROMPT_PROFILE,
) -> dict[str, object]:
    if variant not in VARIANTS:
        raise ValueError(f"Unknown system ablation variant: {variant}")
    checkpoint = load_checkpoint(trace_path) if resume else {}
    if not resume:
        trace_path.write_text("", encoding="utf-8")
    results_by_id = {
        benchmark_id: compact_arm_checkpoint(record)
        for benchmark_id, record in checkpoint.items()
    }
    used_tokens = sum(
        int(item.get("additional_tokens") or 0) for item in results_by_id.values()
    )
    problem_by_id = {str(item["benchmark_id"]): item for item in problems}
    for problem_index, problem_record in enumerate(problems):
        benchmark_id = str(problem_record["benchmark_id"])
        if benchmark_id in results_by_id:
            continue
        baseline = baseline_by_id.get(benchmark_id)
        if baseline is None:
            raise ValueError(f"Baseline is missing benchmark ID: {benchmark_id}")
        started = time.perf_counter()
        if baseline.get("status") != "completed":
            result = {
                "benchmark_id": benchmark_id,
                "subject": problem_record["subject"],
                "level": problem_record["level"],
                "status": "baseline_failed",
                "repair_attempted": False,
                "additional_model_calls": 0,
                "additional_tokens": 0,
                "budget_skipped": False,
                "failure": baseline.get("failure", "baseline generation failed"),
                "elapsed_seconds": 0.0,
            }
            append_jsonl_record(trace_path, result)
            results_by_id[benchmark_id] = result
            continue
        problem = str(problem_record["problem"])
        steps = list(baseline.get("initial_steps", []))
        initial_answer = extract_final_answer(
            steps, str(baseline.get("raw_response", ""))
        )
        initial_correct = answers_equivalent(
            str(problem_record["answer"]), initial_answer
        )
        # The primary evaluation must not use the reference answer to decide
        # whether repair is needed. The verifier makes that decision; the
        # reference answer is used only below for post-hoc scoring.
        prediction, nodes = predict_for_variant(
            variant, problem, steps, full_verifier, no_graph_verifier
        )
        candidate: list[str] = []
        valid_prefix: list[str] = []
        raw_response = ""
        metadata: dict[str, object] = {}
        repair_failure = ""
        repair_normalized = False
        budget_skipped = False
        attempted = False
        repair_accepted = False
        repair_rejection_reason = ""
        if prediction["error_location"]:
            remaining = None if budget is None else budget - used_tokens
            problem_budget = (
                int((per_problem_budgets or {}).get(benchmark_id, 0))
                if budget is not None
                else None
            )
            expected_prompt = (
                int((expected_prompt_tokens or {}).get(benchmark_id, 0))
                if budget is not None
                else 0
            )
            if (
                remaining is not None
                and (
                    remaining <= max(1, expected_prompt)
                    or problem_budget is None
                    or problem_budget <= max(1, expected_prompt)
                )
            ):
                budget_skipped = True
            else:
                completion_cap = max_output_tokens
                if remaining is not None:
                    completion_cap = min(
                        completion_cap,
                        max(1, remaining - expected_prompt),
                        max(1, int(problem_budget) - expected_prompt),
                    )
                run_seed = seed + problem_index
                model = (
                    model_factory(run_seed, completion_cap)
                    if model_factory
                    else OllamaMathModel(
                        model_name,
                        seed=run_seed,
                        temperature=temperature,
                        timeout_seconds=timeout_seconds,
                        max_output_tokens=completion_cap,
                        prompt_profile=prompt_profile,
                        problem_format="text",
                    )
                )
                error_index = next(
                    index
                    for index, node in enumerate(nodes)
                    if node["node_id"] == prediction["error_location"]
                )
                step_index = max(0, error_index - 1)
                valid_prefix = steps[:step_index]
                bad_step = steps[step_index] if steps else ""
                attempted = True
                for repair_attempt in range(1, 3):
                    try:
                        candidate = model.repair_text(
                            problem,
                            valid_prefix,
                            bad_step,
                            str(prediction["error_type"]),
                            repair_attempt,
                        )
                        repair_failure = ""
                        break
                    except Exception as error:
                        repair_failure = str(error)
                        raw_response = str(getattr(model, "last_repair_raw_response", ""))
                        if raw_response:
                            try:
                                candidate = parse_normalized_text_steps(raw_response)
                                repair_failure = ""
                                repair_normalized = True
                                break
                            except ValueError:
                                pass
                raw_response = str(getattr(model, "last_repair_raw_response", raw_response))
                metadata = dict(getattr(model, "last_repair_metadata", {}))
                used_tokens += token_count(metadata)
        if candidate:
            decision = compare_repair_states(problem, list(steps), valid_prefix + candidate)
            repair_accepted = decision.accepted
            if decision.accepted:
                final_steps = valid_prefix + candidate
                final_answer = extract_final_answer(final_steps, raw_response)
            else:
                repair_rejection_reason = decision.reason
                final_steps = steps
                final_answer = initial_answer
        else:
            if attempted:
                repair_rejection_reason = "No repair candidate was generated."
            final_steps = steps
            final_answer = initial_answer
        final_correct = answers_equivalent(str(problem_record["answer"]), final_answer)
        result = {
            "benchmark_id": benchmark_id,
            "subject": problem_record["subject"],
            "level": problem_record["level"],
            "status": "completed",
            "initial_answer": initial_answer,
            "initial_answer_correct": initial_correct,
            "predicted_error_location": prediction["error_location"],
            "predicted_error_type": prediction["error_type"],
            "prediction_source": prediction["prediction_source"],
            "location_confidence": prediction["location_confidence"],
            "repair_attempted": attempted,
            "repair_generation_succeeded": bool(candidate),
            "repair_accepted": repair_accepted,
            "repair_rejection_reason": repair_rejection_reason,
            "repair_success": attempted and not initial_correct and final_correct,
            "final_answer": final_answer,
            "final_answer_correct": final_correct,
            "repair_regression": attempted and initial_correct and not final_correct,
            "additional_model_calls": int(attempted),
            "additional_prompt_tokens": int(metadata.get("prompt_eval_count", 0)),
            "additional_tokens": token_count(metadata),
            "budget_skipped": budget_skipped,
            "elapsed_seconds": round(time.perf_counter() - started, 3),
            "failure": repair_failure,
        }
        append_jsonl_record(
            trace_path,
            {
                **result,
                "variant_id": variant,
                "problem": problem,
                "reference_answer": problem_record["answer"],
                "reasoning_graph": nodes,
                "initial_steps": steps,
                "final_steps": final_steps,
                "repair_raw_response": raw_response,
                "repair_generation_metadata": metadata,
                "repair_normalized_output_recovery": repair_normalized,
            },
        )
        results_by_id[benchmark_id] = result
        print(
            f"[{variant}] {len(results_by_id)}/{len(problems)} "
            f"calls={result['additional_model_calls']} tokens={result['additional_tokens']}"
        )
    results = [
        results_by_id[str(item["benchmark_id"])]
        for item in problems
        if str(item["benchmark_id"]) in results_by_id
    ]
    return summarize_arm(variant, results, len(problems), budget)


def run_system_ablation(
    problems: list[dict[str, object]],
    baseline_records: list[dict[str, object]],
    full_verifier: LearnedTypedVerifier,
    no_graph_verifier: LearnedTypedVerifier,
    model_name: str,
    trace_prefix: Path,
    *,
    seed: int = 42,
    temperature: float = 0.0,
    timeout_seconds: int = 60,
    max_output_tokens: int = 192,
    model_factory: Callable[[int, int], object] | None = None,
    resume: bool = False,
    prompt_profile: str = FROZEN_PROMPT_PROFILE,
) -> dict[str, object]:
    baseline_by_id = {
        str(record["benchmark_id"]): record for record in baseline_records
    }
    arms: list[dict[str, object]] = []
    full_trace = trace_prefix.with_name(trace_prefix.name + "_full_mathrepair.jsonl")
    full = run_arm(
        "full_mathrepair",
        problems,
        baseline_by_id,
        full_verifier,
        no_graph_verifier,
        model_name,
        full_trace,
        seed=seed,
        temperature=temperature,
        timeout_seconds=timeout_seconds,
        max_output_tokens=max_output_tokens,
        budget=None,
        model_factory=model_factory,
        resume=resume,
        prompt_profile=prompt_profile,
    )
    matched_budget = int(full["additional_tokens"])
    full["matched_additional_token_budget"] = matched_budget
    full["budget_respected"] = True
    arms.append(full)
    expected_prompt_tokens = {
        str(item["benchmark_id"]): int(item.get("additional_prompt_tokens") or 0)
        for item in full["results"]
    }
    per_problem_budgets = {
        str(item["benchmark_id"]): int(item.get("additional_tokens") or 0)
        for item in full["results"]
    }
    for variant in VARIANTS[1:]:
        trace_path = trace_prefix.with_name(trace_prefix.name + f"_{variant}.jsonl")
        arms.append(
            run_arm(
                variant,
                problems,
                baseline_by_id,
                full_verifier,
                no_graph_verifier,
                model_name,
                trace_path,
                seed=seed,
                temperature=temperature,
                timeout_seconds=timeout_seconds,
                max_output_tokens=max_output_tokens,
                budget=matched_budget,
                expected_prompt_tokens=expected_prompt_tokens,
                per_problem_budgets=per_problem_budgets,
                model_factory=model_factory,
                resume=resume,
                prompt_profile=prompt_profile,
            )
        )
    baseline_generation_tokens = sum(
        token_count(dict(record.get("generation_metadata", {})))
        for record in baseline_records
    )
    baseline_model_calls = len(problems)
    for arm in arms:
        arm["total_model_calls_including_baseline"] = (
            baseline_model_calls + int(arm["additional_model_calls"])
        )
        arm["average_model_calls_including_baseline"] = (
            arm["total_model_calls_including_baseline"] / len(problems)
        )
        arm["total_tokens_including_baseline"] = (
            baseline_generation_tokens + int(arm["additional_tokens"])
        )
        arm["average_tokens_including_baseline"] = (
            arm["total_tokens_including_baseline"] / len(problems)
        )
    return {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "experiment": "math500_system_component_ablation",
        "benchmark": "MATH-500 hard subset",
        "model": model_name,
        "problem_count": len(problems),
        "base_seed": seed,
        "temperature": temperature,
        "max_repair_output_tokens": max_output_tokens,
        "matched_additional_token_budget": matched_budget,
        "baseline_model_calls": baseline_model_calls,
        "baseline_generation_tokens": baseline_generation_tokens,
        "matched_budget_comparison_valid": all(
            bool(arm["budget_respected"]) for arm in arms
        ),
        "baseline_reused_across_arms": True,
        "reference_answer_usage": "post-repair scoring only",
        "variants": arms,
        "interpretation_rule": (
            "Only final-answer and repair metrics are system-level. Error-location "
            "and type correctness cannot be measured without natural-trace labels."
        ),
        "symbolic_support_observation": (
            "The structural/symbolic heuristic abstained on every completed open-ended "
            "MATH trace, so full and no-symbolic use the same learned predictions."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--problems", type=Path, default=DEFAULT_PROBLEMS)
    parser.add_argument("--baseline-traces", type=Path, default=DEFAULT_BASELINE)
    parser.add_argument("--verifier", type=Path, default=DEFAULT_VERIFIER)
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument(
        "--trace-prefix", type=Path, default=PROJECT_DIR / "math500_system_ablation"
    )
    parser.add_argument("--model", default=FROZEN_MODEL)
    parser.add_argument("--seed", type=int, default=FROZEN_BASE_SEED)
    parser.add_argument("--temperature", type=float, default=FROZEN_TEMPERATURE)
    parser.add_argument("--timeout-seconds", type=int, default=60)
    parser.add_argument("--max-output-tokens", type=int, default=192)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--allow-larger-benchmark", action="store_true")
    parser.add_argument("--allow-protocol-change", action="store_true")
    args = parser.parse_args()
    try:
        problems = load_pilot(args.problems, limit=None)
        require_frozen_base(
            problem_count=len(problems),
            model=args.model,
            temperature=args.temperature,
            base_seed=args.seed,
            allow_larger=args.allow_larger_benchmark,
            allow_change=args.allow_protocol_change,
        )
        baseline = load_trace_records(args.baseline_traces)
        full_verifier = joblib.load(args.verifier)
        if not isinstance(full_verifier, LearnedTypedVerifier):
            raise ValueError("Verifier artifact has the wrong type.")
        no_graph_verifier, _ = train_verifier(
            load_examples(args.dataset), seed=args.seed, include_graph=False
        )
        report = run_system_ablation(
            problems,
            baseline,
            full_verifier,
            no_graph_verifier,
            args.model,
            args.trace_prefix,
            seed=args.seed,
            temperature=args.temperature,
            timeout_seconds=args.timeout_seconds,
            max_output_tokens=args.max_output_tokens,
            resume=args.resume,
            prompt_profile=FROZEN_PROMPT_PROFILE,
        )
        args.report.write_text(
            json.dumps(report, indent=2, ensure_ascii=True) + "\n", encoding="utf-8"
        )
    except (OSError, ValueError, TypeError, ProtocolDrift) as error:
        parser.error(str(error))
    for arm in report["variants"]:
        print(
            f"{arm['variant_id']}: final={arm['final_answer_accuracy']:.1%}, "
            f"repair={arm['repair_success_rate']:.1%}, "
            f"tokens={arm['additional_tokens']}"
        )
    print(f"Matched budget: {report['matched_additional_token_budget']} tokens")
    print(f"Report: {args.report}")


if __name__ == "__main__":
    main()
