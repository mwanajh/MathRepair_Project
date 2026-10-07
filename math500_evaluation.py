"""Run answer-scored MATH-500 evaluation with learned verification and repair."""

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
    FROZEN_BASELINE_REPAIR_ATTEMPTS,
    FROZEN_MAX_OUTPUT_TOKENS,
    FROZEN_MODEL,
    FROZEN_PROMPT_PROFILE,
    FROZEN_TEMPERATURE,
    FROZEN_TIMEOUT_SECONDS,
    ProtocolDrift,
    require_generation_protocol,
)
from learned_verifier import LearnedTypedVerifier
from math_answer_scoring import answers_equivalent, extract_final_answer
from model_pipeline import (
    OllamaMathModel,
    append_jsonl_record,
    parse_normalized_text_steps,
)


DEFAULT_PROBLEMS = Path(__file__).with_name("math500_pilot_40.json")
DEFAULT_VERIFIER = Path(__file__).with_name("learned_verifier_model.joblib")
DEFAULT_TRACES = Path(__file__).with_name("math500_accuracy_traces.jsonl")
DEFAULT_REPORT = Path(__file__).with_name("math500_accuracy_report.json")


def trace_nodes(problem: str, steps: list[str], *, graph: bool = True) -> list[dict[str, object]]:
    """Create inference records matching the learned verifier's node contract."""
    states = [problem] + steps
    records = []
    for index, state in enumerate(states):
        records.append(
            {
                "node_id": f"n{index + 1}",
                "state": state,
                "model_generated_reasoning": state,
                "depends_on": [f"n{index}"] if graph and index else [],
                "subgoal": "problem" if index == 0 else "advance solution",
                "assumptions": [],
            }
        )
    return records


def token_count(metadata: dict[str, object]) -> int:
    return int(metadata.get("prompt_eval_count", 0)) + int(metadata.get("eval_count", 0))


def load_checkpoint(path: Path) -> dict[str, dict[str, object]]:
    """Load the latest preserved result for each benchmark ID."""
    records: dict[str, dict[str, object]] = {}
    if not path.exists():
        return records
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError as error:
            raise ValueError(f"Invalid checkpoint JSON at line {line_number}.") from error
        benchmark_id = record.get("benchmark_id") if isinstance(record, dict) else None
        if not isinstance(benchmark_id, str) or not benchmark_id:
            raise ValueError(f"Checkpoint line {line_number} has no benchmark_id.")
        records[benchmark_id] = record
    return records


def summarize(results: list[dict[str, object]], model: str) -> dict[str, object]:
    completed = [item for item in results if item["status"] == "completed"]
    repair_attempts = [item for item in completed if item["repair_attempted"]]
    initial_correct = sum(bool(item["initial_answer_correct"]) for item in completed)
    final_correct = sum(bool(item["final_answer_correct"]) for item in completed)
    repairs_succeeded = sum(bool(item["repair_success"]) for item in repair_attempts)
    detected = [item for item in completed if item["predicted_error_location"]]
    strict_contract = sum(bool(item["strict_output_contract"]) for item in completed)
    total_calls = sum(int(item["model_call_count"]) for item in results)
    total_tokens = sum(int(item["total_tokens"]) for item in results)
    denominator = len(results)
    return {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "benchmark": "MATH-500 hard subset",
        "model": model,
        "problem_count": denominator,
        "completed_count": len(completed),
        "failure_count": denominator - len(completed),
        "strict_output_contract_count": strict_contract,
        "strict_output_contract_rate": strict_contract / denominator if denominator else 0.0,
        "normalized_recovery_count": sum(
            bool(item["normalized_output_recovery"]) for item in completed
        ),
        "initial_answer_correct_count": initial_correct,
        "initial_answer_accuracy": initial_correct / denominator if denominator else 0.0,
        "final_answer_correct_count": final_correct,
        "final_answer_accuracy": final_correct / denominator if denominator else 0.0,
        "verifier_detection_count": len(detected),
        "verifier_detection_rate": len(detected) / len(completed) if completed else 0.0,
        "predicted_error_type_counts": dict(
            Counter(str(item["predicted_error_type"]) for item in detected)
        ),
        "repair_attempt_count": len(repair_attempts),
        "repair_success_count": repairs_succeeded,
        "repair_success_rate": repairs_succeeded / len(repair_attempts) if repair_attempts else 0.0,
        "wrong_to_correct_count": sum(
            not bool(item["initial_answer_correct"]) and bool(item["final_answer_correct"])
            for item in completed
        ),
        "repair_regression_count": sum(
            bool(item["initial_answer_correct"]) and not bool(item["final_answer_correct"])
            for item in completed
        ),
        "total_model_calls": total_calls,
        "average_model_calls": total_calls / denominator if denominator else 0.0,
        "total_tokens": total_tokens,
        "average_tokens": total_tokens / denominator if denominator else 0.0,
        "reference_answer_usage": "post-generation scoring only",
        "results": results,
    }


def evaluate_math500(
    problems: list[dict[str, object]],
    verifier: LearnedTypedVerifier,
    model_name: str,
    traces: Path,
    *,
    model_factory: Callable[[int], object] | None = None,
    repair_attempts: int = 1,
    seed: int = 42,
    temperature: float = 0.0,
    timeout_seconds: int = 120,
    max_output_tokens: int | None = FROZEN_MAX_OUTPUT_TOKENS,
    prompt_profile: str = "default",
    resume: bool = False,
) -> dict[str, object]:
    """Evaluate generation, learned verification, local repair, and cost."""
    if repair_attempts < 0:
        raise ValueError("repair_attempts cannot be negative.")
    if timeout_seconds < 1:
        raise ValueError("timeout_seconds must be positive.")
    checkpoint = load_checkpoint(traces) if resume else {}
    if not resume:
        traces.write_text("", encoding="utf-8")
    result_by_id: dict[str, dict[str, object]] = dict(checkpoint)
    for index, record in enumerate(problems):
        benchmark_id = str(record["benchmark_id"])
        if benchmark_id in checkpoint:
            continue
        run_seed = seed + index
        model = (
            model_factory(run_seed)
            if model_factory
            else OllamaMathModel(
                model_name,
                seed=run_seed,
                temperature=temperature,
                timeout_seconds=timeout_seconds,
                max_output_tokens=max_output_tokens,
                prompt_profile=prompt_profile,
                problem_format="text",
            )
        )
        started = time.perf_counter()
        calls = 0
        tokens = 0
        raw_repairs: list[dict[str, object]] = []
        try:
            normalized_output_recovery = False
            try:
                steps = model.solve(str(record["problem"]))
            except ValueError:
                raw_response = str(getattr(model, "last_raw_response", ""))
                if not raw_response:
                    raise
                steps = parse_normalized_text_steps(raw_response)
                normalized_output_recovery = True
            calls += 1
            generation_metadata = dict(getattr(model, "last_metadata", {}))
            tokens += token_count(generation_metadata)
            initial_answer = extract_final_answer(
                steps, str(getattr(model, "last_raw_response", ""))
            )
            initial_correct = answers_equivalent(str(record["answer"]), initial_answer)
            nodes = trace_nodes(str(record["problem"]), steps)
            prediction = verifier.predict(str(record["problem"]), nodes)
            repaired_steps: list[str] = []
            repair_method = getattr(model, "repair_text", None)
            if prediction["error_location"] and repair_attempts and repair_method:
                error_index = next(
                    i for i, node in enumerate(nodes) if node["node_id"] == prediction["error_location"]
                )
                step_index = max(0, error_index - 1)
                valid_prefix = steps[:step_index]
                bad_step = steps[step_index] if steps else ""
                for attempt_index in range(1, repair_attempts + 1):
                    calls += 1
                    candidate: list[str] = []
                    repair_failure = ""
                    repair_normalized = False
                    try:
                        candidate = repair_method(
                            str(record["problem"]),
                            valid_prefix,
                            bad_step,
                            str(prediction["error_type"]),
                            attempt_index,
                        )
                    except Exception as error:
                        repair_failure = str(error)
                        repair_raw = str(
                            getattr(model, "last_repair_raw_response", "")
                        )
                        if repair_raw:
                            try:
                                candidate = parse_normalized_text_steps(repair_raw)
                                repair_failure = ""
                                repair_normalized = True
                            except ValueError:
                                pass
                    repair_metadata = dict(getattr(model, "last_repair_metadata", {}))
                    tokens += token_count(repair_metadata)
                    raw_repairs.append(
                        {
                            "attempt_index": attempt_index,
                            "steps": candidate,
                            "raw_response": str(getattr(model, "last_repair_raw_response", "")),
                            "generation_metadata": repair_metadata,
                            "failure": repair_failure,
                            "normalized_output_recovery": repair_normalized,
                        }
                    )
                    if candidate:
                        repaired_steps = valid_prefix + candidate
                        break
            final_steps = repaired_steps or steps
            final_answer = extract_final_answer(
                final_steps,
                raw_repairs[-1]["raw_response"] if repaired_steps and raw_repairs else "",
            )
            final_correct = answers_equivalent(str(record["answer"]), final_answer)
            result = {
                "benchmark_id": benchmark_id,
                "subject": record["subject"],
                "level": record["level"],
                "status": "completed",
                "seed": run_seed,
                "strict_output_contract": not normalized_output_recovery,
                "normalized_output_recovery": normalized_output_recovery,
                "initial_answer": initial_answer,
                "initial_answer_correct": initial_correct,
                "predicted_error_location": prediction["error_location"],
                "predicted_error_type": prediction["error_type"],
                "location_confidence": prediction["location_confidence"],
                "repair_attempted": bool(raw_repairs),
                "repair_generation_succeeded": bool(repaired_steps),
                "repair_success": bool(raw_repairs) and (not initial_correct) and final_correct,
                "final_answer": final_answer,
                "final_answer_correct": final_correct,
                "model_call_count": calls,
                "generation_tokens": token_count(generation_metadata),
                "repair_tokens": tokens - token_count(generation_metadata),
                "total_tokens": tokens,
                "elapsed_seconds": round(time.perf_counter() - started, 3),
            }
            append_jsonl_record(
                traces,
                {
                    **result,
                    "model": model_name,
                    "protocol": {
                        "base_seed": seed,
                        "temperature": temperature,
                        "repair_attempts_per_detection": repair_attempts,
                        "timeout_seconds": timeout_seconds,
                        "max_output_tokens": max_output_tokens,
                    },
                    "problem": record["problem"],
                    "reference_answer": record["answer"],
                    "initial_steps": steps,
                    "reasoning_graph": nodes,
                    "raw_response": str(getattr(model, "last_raw_response", "")),
                    "generation_metadata": generation_metadata,
                    "repair_attempts": raw_repairs,
                },
            )
        except Exception as error:
            failure_metadata = dict(getattr(model, "last_metadata", {}))
            if not tokens:
                tokens = token_count(failure_metadata)
            result = {
                "benchmark_id": benchmark_id,
                "subject": record["subject"],
                "level": record["level"],
                "status": "failed",
                "failure": str(error),
                "model_call_count": max(1, calls),
                "total_tokens": tokens,
                "elapsed_seconds": round(time.perf_counter() - started, 3),
            }
            append_jsonl_record(
                traces,
                {
                    **result,
                    "model": model_name,
                    "protocol": {
                        "base_seed": seed,
                        "temperature": temperature,
                        "repair_attempts_per_detection": repair_attempts,
                        "timeout_seconds": timeout_seconds,
                        "max_output_tokens": max_output_tokens,
                    },
                    "problem": record["problem"],
                    "raw_response": str(getattr(model, "last_raw_response", "")),
                    "generation_metadata": failure_metadata,
                    "repair_raw_response": str(
                        getattr(model, "last_repair_raw_response", "")
                    ),
                    "repair_generation_metadata": dict(
                        getattr(model, "last_repair_metadata", {})
                    ),
                },
            )
        result_by_id[benchmark_id] = result
    results = [
        result_by_id[str(record["benchmark_id"])]
        for record in problems
        if str(record["benchmark_id"]) in result_by_id
    ]
    report = summarize(results, model_name)
    report.update(
        {
            "base_seed": seed,
            "temperature": temperature,
            "repair_attempts_per_detection": repair_attempts,
            "verifier_location_threshold": verifier.location_threshold,
            "verifier_uses_graph_features": verifier.include_graph,
            "answer_scorer": "normalized_exact_symbolic_v1",
            "timeout_seconds": timeout_seconds,
            "max_output_tokens": max_output_tokens,
            "prompt_profile": prompt_profile,
            "resumed_from_checkpoint": resume,
        }
    )
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--problems", type=Path, default=DEFAULT_PROBLEMS)
    parser.add_argument("--verifier", type=Path, default=DEFAULT_VERIFIER)
    parser.add_argument("--traces", type=Path, default=DEFAULT_TRACES)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--model", default=FROZEN_MODEL)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--seed", type=int, default=FROZEN_BASE_SEED)
    parser.add_argument("--temperature", type=float, default=FROZEN_TEMPERATURE)
    parser.add_argument(
        "--repair-attempts", type=int, default=FROZEN_BASELINE_REPAIR_ATTEMPTS
    )
    parser.add_argument("--timeout-seconds", type=int, default=FROZEN_TIMEOUT_SECONDS)
    parser.add_argument("--max-output-tokens", type=int, default=FROZEN_MAX_OUTPUT_TOKENS)
    parser.add_argument(
        "--prompt-profile",
        choices=(
            "default",
            "qwen2_math_json",
            "stable_text_json",
            "closed_text_json",
        ),
        default=FROZEN_PROMPT_PROFILE,
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Keep completed checkpoint records and run only missing benchmark IDs.",
    )
    parser.add_argument(
        "--allow-larger-benchmark",
        action="store_true",
        help="Permit more problems than the measured stability pilot.",
    )
    parser.add_argument(
        "--allow-protocol-change",
        action="store_true",
        help="Permit a model or output setting outside the frozen protocol.",
    )
    args = parser.parse_args()
    if args.limit is not None and args.limit < 1:
        parser.error("--limit must be at least 1.")
    try:
        problems = load_pilot(args.problems, args.limit)
        require_generation_protocol(
            problem_count=len(problems),
            model=args.model,
            prompt_profile=args.prompt_profile,
            temperature=args.temperature,
            base_seed=args.seed,
            max_output_tokens=args.max_output_tokens,
            repair_attempts=args.repair_attempts,
            allow_larger=args.allow_larger_benchmark,
            allow_change=args.allow_protocol_change,
        )
        verifier = joblib.load(args.verifier)
        if not isinstance(verifier, LearnedTypedVerifier):
            raise ValueError("Verifier artifact has the wrong type.")
        report = evaluate_math500(
            problems,
            verifier,
            args.model,
            args.traces,
            repair_attempts=args.repair_attempts,
            seed=args.seed,
            temperature=args.temperature,
            timeout_seconds=args.timeout_seconds,
            max_output_tokens=args.max_output_tokens,
            prompt_profile=args.prompt_profile,
            resume=args.resume,
        )
        args.report.write_text(
            json.dumps(report, indent=2, ensure_ascii=True) + "\n", encoding="utf-8"
        )
    except (OSError, ValueError, TypeError, ProtocolDrift) as error:
        parser.error(str(error))
    print(
        f"Initial accuracy: {report['initial_answer_correct_count']}/"
        f"{report['problem_count']} ({report['initial_answer_accuracy']:.1%})"
    )
    print(
        f"Final accuracy: {report['final_answer_correct_count']}/"
        f"{report['problem_count']} ({report['final_answer_accuracy']:.1%})"
    )
    print(f"Report: {args.report}")
    print(f"Raw traces: {args.traces}")


if __name__ == "__main__":
    main()
