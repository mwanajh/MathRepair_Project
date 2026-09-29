"""Recompute MATH-500 answer metrics from preserved raw trace records."""

import argparse
import json
from pathlib import Path

from math500_evaluation import summarize
from math_answer_scoring import answers_equivalent, extract_final_answer


def load_trace_records(path: Path) -> list[dict[str, object]]:
    records = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        try:
            record = json.loads(line)
        except json.JSONDecodeError as error:
            raise ValueError(f"Invalid trace JSON at line {line_number}.") from error
        if not isinstance(record, dict):
            raise ValueError(f"Trace line {line_number} is not an object.")
        records.append(record)
    if not records:
        raise ValueError("Trace file is empty.")
    return records


def compact_rescored_result(record: dict[str, object]) -> dict[str, object]:
    if record.get("status") != "completed":
        return {
            key: record.get(key)
            for key in (
                "benchmark_id",
                "subject",
                "level",
                "status",
                "failure",
                "model_call_count",
                "total_tokens",
                "elapsed_seconds",
            )
        }
    expected = str(record["reference_answer"])
    initial_steps = list(record.get("initial_steps", []))
    initial_answer = extract_final_answer(
        initial_steps, str(record.get("raw_response", ""))
    )
    initial_correct = answers_equivalent(expected, initial_answer)
    final_steps = initial_steps
    final_raw = ""
    successful_repairs = [
        attempt
        for attempt in record.get("repair_attempts", [])
        if isinstance(attempt, dict) and attempt.get("steps")
    ]
    if successful_repairs:
        error_node = str(record.get("predicted_error_location", "n2"))
        try:
            step_index = max(0, int(error_node.lstrip("n")) - 2)
        except ValueError:
            step_index = 0
        selected = successful_repairs[0]
        final_steps = initial_steps[:step_index] + list(selected["steps"])
        final_raw = str(selected.get("raw_response", ""))
    final_answer = extract_final_answer(final_steps, final_raw)
    final_correct = answers_equivalent(expected, final_answer)
    result = {
        key: record.get(key)
        for key in (
            "benchmark_id",
            "subject",
            "level",
            "status",
            "seed",
            "strict_output_contract",
            "normalized_output_recovery",
            "predicted_error_location",
            "predicted_error_type",
            "location_confidence",
            "repair_attempted",
            "repair_generation_succeeded",
            "model_call_count",
            "generation_tokens",
            "repair_tokens",
            "total_tokens",
            "elapsed_seconds",
        )
    }
    result.update(
        {
            "initial_answer": initial_answer,
            "initial_answer_correct": initial_correct,
            "repair_success": bool(successful_repairs) and not initial_correct and final_correct,
            "final_answer": final_answer,
            "final_answer_correct": final_correct,
        }
    )
    return result


def rescore(path: Path, model: str) -> dict[str, object]:
    records = load_trace_records(path)
    report = summarize(
        [compact_rescored_result(record) for record in records],
        model,
    )
    recorded_seeds = [
        int(record["seed"])
        for record in records
        if record.get("seed") is not None
    ]
    recorded_temperatures = [
        record.get("generation_metadata", {}).get("temperature")
        for record in records
        if isinstance(record.get("generation_metadata"), dict)
        and record.get("generation_metadata", {}).get("temperature") is not None
    ]
    report.update(
        {
            "rescored_from": path.name,
            "answer_scorer": "normalized_exact_symbolic_v1",
            "base_seed": min(recorded_seeds) if recorded_seeds else None,
            "temperature": recorded_temperatures[0] if recorded_temperatures else None,
            "repair_attempts_per_detection": max(
                (len(record.get("repair_attempts", [])) for record in records),
                default=0,
            ),
        }
    )
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--traces", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--model", required=True)
    args = parser.parse_args()
    try:
        report = rescore(args.traces, args.model)
        args.report.write_text(
            json.dumps(report, indent=2, ensure_ascii=True) + "\n", encoding="utf-8"
        )
    except (OSError, ValueError, TypeError) as error:
        parser.error(str(error))
    print(
        f"Rescored initial/final accuracy: {report['initial_answer_accuracy']:.1%} / "
        f"{report['final_answer_accuracy']:.1%}"
    )
    print(f"Report: {args.report}")


if __name__ == "__main__":
    main()
