"""Compare local repair with verified global regeneration under matched budgets."""

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import time
from typing import Callable

from collect_model_traces import answers_match
from model_pipeline import OllamaMathModel, select_model_answer_step
from model_repair import has_isolated_answer
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


def run_matched_budget(
    report: dict[str, object],
    model_factory: Callable[[dict[str, object], int, int], object] | None = None,
) -> dict[str, object]:
    """Use each local-repair token budget for one full-solution regeneration."""
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

    global_results: list[dict[str, object]] = []
    for run_number, record in enumerate(error_runs, start=1):
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
    budget_violations = sum(
        not bool(item.get("budget_respected", False)) for item in global_results
    )

    return {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "source": {
            "model": report.get("model", ""),
            "run_count": total_runs,
            "completed_count": len(completed),
            "failure_count": len(failed),
            "detected_error_runs": len(error_runs),
            "temperature": report.get("temperature", 0.0),
        },
        "budget_definition": (
            "Per error run, global prompt plus completion tokens may not exceed "
            "the prompt plus completion tokens used by local model repair."
        ),
        "local_repair_additional_token_budget": local_budget,
        "global_regeneration_additional_tokens": global_tokens,
        "global_budget_utilization_rate": safe_rate(global_tokens, local_budget),
        "budget_violation_count": budget_violations,
        "matched_budget_comparison_valid": budget_violations == 0,
        "strategies": [
            {
                "name": "no_repair",
                "answer_correct": baseline_answer_correct,
                "answer_accuracy": safe_rate(baseline_answer_correct, total_runs),
                "trace_valid": baseline_trace_valid,
                "trace_valid_rate": safe_rate(baseline_trace_valid, total_runs),
                "additional_model_calls": 0,
                "additional_tokens": 0,
            },
            {
                "name": "verified_global_regeneration",
                "answer_correct": global_answer_correct,
                "answer_accuracy": safe_rate(global_answer_correct, total_runs),
                "trace_valid": global_trace_valid,
                "trace_valid_rate": safe_rate(global_trace_valid, total_runs),
                "accepted_repairs": global_accepted,
                "additional_model_calls": global_call_count,
                "additional_tokens": global_tokens,
            },
            {
                "name": "verified_local_repair",
                "answer_correct": local_answer_correct,
                "answer_accuracy": safe_rate(local_answer_correct, total_runs),
                "trace_valid": local_trace_valid,
                "trace_valid_rate": safe_rate(local_trace_valid, total_runs),
                "accepted_repairs": int(report.get("model_repair_accept_count", 0)),
                "additional_model_calls": int(
                    report.get("model_repair_attempt_count", 0)
                ),
                "additional_tokens": local_budget,
            },
        ],
        "global_regeneration_results": global_results,
        "caveats": ([
            "This is a small stress set and not a benchmark result.",
            "Both repair strategies use the same symbolic verifier gate.",
            "Global regeneration retries only while its per-error budget remains.",
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
        "| Strategy | Answer accuracy | Valid traces | Extra calls | Extra tokens |",
        "|---|---:|---:|---:|---:|",
    ]
    for strategy in summary["strategies"]:
        lines.append(
            f"| {strategy['name']} | {percent(strategy['answer_accuracy'])} "
            f"({strategy['answer_correct']}/{source['run_count']}) | "
            f"{percent(strategy['trace_valid_rate'])} "
            f"({strategy['trace_valid']}/{source['run_count']}) | "
            f"{strategy['additional_model_calls']} | "
            f"{strategy['additional_tokens']:,} |"
        )
    lines.extend(
        [
            "",
            (
                "Global budget utilization: "
                f"{percent(summary['global_budget_utilization_rate'])}"
            ),
            (
                "Matched-budget comparison valid: "
                f"**{summary['matched_budget_comparison_valid']}**"
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
    args = parser.parse_args()

    with args.input.open(encoding="utf-8") as file:
        report = json.load(file)
    summary = run_matched_budget(report)
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
            f"extra_tokens={strategy['additional_tokens']}"
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
