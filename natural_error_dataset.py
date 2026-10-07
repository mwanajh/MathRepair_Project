"""Annotation contract for natural model traces.

The queue is built from saved MATH-500 generations, plus reviewed equation
traces when a saved model step shows an error type missing from that set.
Answer correctness is kept only as a sampling field. Error location, error
type, and recovery action stay empty until a trace is reviewed. The reference
answer is never copied into the annotation record.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from error_taxonomy import ERROR_TYPE_CODES, VALID_NO_REPAIR
from math500_evaluation import load_checkpoint, trace_nodes


PROJECT_DIR = Path(__file__).resolve().parent
DEFAULT_TRACES = PROJECT_DIR / "math500_full40_baseline_traces.jsonl"
DEFAULT_REPORT = PROJECT_DIR / "math500_full40_baseline_report.json"
DEFAULT_OUTPUT = PROJECT_DIR / "natural_error_annotation_queue.json"
DEFAULT_REVIEWS = PROJECT_DIR / "natural_error_reviews.json"
DEFAULT_STATISTICS = PROJECT_DIR / "natural_error_dataset_statistics.json"
SUPPLEMENTAL_EQUATION_TRACES = (
    {
        "path": PROJECT_DIR / "stress_multisample_traces.jsonl",
        "line_number": 13,
        "benchmark_id": "stress-multisample/13",
        "subject": "algebra",
    },
)
SUPPLEMENTAL_CHECKPOINT_TRACES = (
    {
        "path": PROJECT_DIR / "stability_pilot_qwen2_5_3b_stable_traces.jsonl",
        "source_benchmark_id": "test/algebra/101.json",
        "benchmark_id": "stability-stable/test/algebra/101.json",
    },
    {
        "path": PROJECT_DIR / "stability_pilot_qwen2_5_3b_stable_traces.jsonl",
        "source_benchmark_id": "test/algebra/1031.json",
        "benchmark_id": "stability-stable/test/algebra/1031.json",
    },
    {
        "path": PROJECT_DIR / "stability_pilot_qwen2_5_3b_stable_traces.jsonl",
        "source_benchmark_id": "test/algebra/1078.json",
        "benchmark_id": "stability-stable/test/algebra/1078.json",
    },
    {
        "path": PROJECT_DIR / "stability_pilot_qwen2_5_3b_traces.jsonl",
        "source_benchmark_id": "test/intermediate_algebra/1111.json",
        "benchmark_id": "stability-qwen2.5-3b/test/intermediate_algebra/1111.json",
    },
    {
        "path": PROJECT_DIR / "natural_error_3b_pair_traces.jsonl",
        "source_benchmark_id": "pair-equations/3n",
        "benchmark_id": "pair-equations/3n",
    },
    {
        "path": PROJECT_DIR / "natural_error_3b_pair_traces.jsonl",
        "source_benchmark_id": "pair-equations/6a",
        "benchmark_id": "pair-equations/6a",
    },
    {
        "path": PROJECT_DIR / "natural_error_3b_pair_traces.jsonl",
        "source_benchmark_id": "pair-equations/6u",
        "benchmark_id": "pair-equations/6u",
    },
    {
        "path": PROJECT_DIR / "natural_error_3b_pair_traces.jsonl",
        "source_benchmark_id": "pair-equations/8d",
        "benchmark_id": "pair-equations/8d",
    },
    {
        "path": PROJECT_DIR / "natural_error_sign_traces.jsonl",
        "source_benchmark_id": "sign-equation/nested-8",
        "benchmark_id": "sign-equation/nested-8",
    },
)

TRACE_VALID = "valid"
TRACE_INVALID = "invalid"
LABEL_UNREVIEWED = "unreviewed"
LABEL_REVIEWED = "reviewed"

RECOVERY_ACTIONS = (
    "CONTINUE",
    "LOCAL_REPAIR",
    "GLOBAL_REGENERATE",
    "TOOL_EXECUTE",
    "REPLAN",
    "BACKTRACK",
)
INVALID_RECOVERY_ACTIONS = tuple(
    action for action in RECOVERY_ACTIONS if action != "CONTINUE"
)

REQUIRED_FIELDS = (
    "example_id",
    "source",
    "benchmark_id",
    "model",
    "subject",
    "level",
    "problem",
    "trace",
    "sampling_answer_correct",
    "label_status",
    "trace_validity",
    "error_location",
    "error_type",
    "recovery_action",
)


def _node_ids(trace: list[dict[str, object]]) -> set[str]:
    return {str(node.get("node_id", "")) for node in trace}


def validate_example(example: dict[str, object], *, index: int = 1) -> None:
    """Reject a record that breaks the natural-error supervision contract."""
    missing = [field for field in REQUIRED_FIELDS if field not in example]
    if missing:
        raise ValueError(f"Example {index} is missing {', '.join(missing)}.")
    if example["source"] != "model_generated":
        raise ValueError(f"Example {index} must come from a model-generated trace.")
    if "reference_answer" in example:
        raise ValueError(f"Example {index} must not store the reference answer.")
    trace = example["trace"]
    if not isinstance(trace, list) or not trace:
        raise ValueError(f"Example {index} needs a non-empty trace.")
    for node in trace:
        if not isinstance(node, dict) or not node.get("node_id") or "state" not in node:
            raise ValueError(f"Example {index} has a trace node without id and state.")
    status = example["label_status"]
    if status == LABEL_UNREVIEWED:
        unlabeled = (
            example["trace_validity"] is None
            and example["error_location"] is None
            and example["error_type"] is None
            and example["recovery_action"] is None
        )
        if not unlabeled:
            raise ValueError(f"Example {index} is unreviewed but already has labels.")
        return
    if status != LABEL_REVIEWED:
        raise ValueError(f"Example {index} has an unknown label status.")
    _validate_reviewed_label(example, index, _node_ids(trace))


def _validate_reviewed_label(
    example: dict[str, object], index: int, node_ids: set[str]
) -> None:
    validity = example["trace_validity"]
    error_type = example["error_type"]
    location = example["error_location"]
    action = example["recovery_action"]
    if validity == TRACE_VALID:
        if error_type != VALID_NO_REPAIR or location is not None or action != "CONTINUE":
            raise ValueError(
                f"Example {index} is valid and must use {VALID_NO_REPAIR} "
                "with no error location and CONTINUE."
            )
        return
    if validity != TRACE_INVALID:
        raise ValueError(f"Example {index} has an unknown trace validity.")
    if error_type not in ERROR_TYPE_CODES:
        raise ValueError(f"Example {index} has an unknown error type.")
    if not isinstance(location, str) or location not in node_ids:
        raise ValueError(f"Example {index} does not name a node in its trace.")
    if action not in INVALID_RECOVERY_ACTIONS:
        raise ValueError(f"Example {index} needs a recovery action other than CONTINUE.")


def _same_equation(left: str, right: str) -> bool:
    return "".join(left.split()) == "".join(right.split())


def equation_checkpoint_record(
    raw: dict[str, object], *, benchmark_id: str, subject: str
) -> dict[str, object]:
    """Convert one saved equation trace without keeping its reference answer."""
    if raw.get("status") != "completed":
        raise ValueError(f"{benchmark_id} is not a completed model trace.")
    steps = [str(step) for step in list(raw.get("steps") or [])]
    if not steps or not str(raw.get("problem", "")).strip():
        raise ValueError(f"{benchmark_id} has no problem or steps.")
    record = {
        "benchmark_id": benchmark_id,
        "status": "completed",
        "model": str(raw.get("model", "")),
        "subject": subject,
        "level": None,
        "problem": str(raw["problem"]),
        "initial_steps": steps,
        "final_answer_correct": _same_equation(steps[-1], str(raw.get("correct_answer", ""))),
    }
    if "reference_answer" in record or "correct_answer" in record:
        raise ValueError(f"{benchmark_id} kept a reference answer.")
    return record


def checkpoint_supplement_record(
    raw: dict[str, object], *, benchmark_id: str
) -> dict[str, object]:
    """Copy one saved MATH-500 generation without its reference answer."""
    if raw.get("status") != "completed":
        raise ValueError(f"{benchmark_id} is not a completed model trace.")
    steps = [str(step) for step in list(raw.get("initial_steps") or [])]
    if not steps or not str(raw.get("problem", "")).strip():
        raise ValueError(f"{benchmark_id} has no problem or steps.")
    record = {
        "benchmark_id": benchmark_id,
        "status": "completed",
        "model": str(raw.get("model", "")),
        "subject": str(raw.get("subject", "")),
        "level": raw.get("level"),
        "problem": str(raw["problem"]),
        "initial_steps": steps,
        "final_answer_correct": bool(raw.get("final_answer_correct")),
    }
    if "reference_answer" in record:
        raise ValueError(f"{benchmark_id} kept a reference answer.")
    return record


def load_checkpoint_supplements(
    specs: tuple[dict[str, object], ...] = SUPPLEMENTAL_CHECKPOINT_TRACES,
) -> dict[str, dict[str, object]]:
    """Load reviewed generations whose original benchmark id would collide."""
    records: dict[str, dict[str, object]] = {}
    for spec in specs:
        source_id = str(spec["source_benchmark_id"])
        matches = []
        for line in Path(spec["path"]).read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            raw = json.loads(line)
            if raw.get("benchmark_id") == source_id and raw.get("status") == "completed":
                matches.append(raw)
        benchmark_id = str(spec["benchmark_id"])
        if len(matches) != 1:
            raise ValueError(f"{benchmark_id} matched {len(matches)} completed traces.")
        records[benchmark_id] = checkpoint_supplement_record(
            matches[0], benchmark_id=benchmark_id
        )
    return records


def load_supplemental_equation_traces(
    specs: tuple[dict[str, object], ...] = SUPPLEMENTAL_EQUATION_TRACES,
) -> dict[str, dict[str, object]]:
    """Load reviewed equation traces from their original saved lines."""
    records: dict[str, dict[str, object]] = {}
    for spec in specs:
        path = Path(spec["path"])
        lines = [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
        line_number = int(spec["line_number"])
        raw = json.loads(lines[line_number - 1])
        benchmark_id = str(spec["benchmark_id"])
        records[benchmark_id] = equation_checkpoint_record(
            raw, benchmark_id=benchmark_id, subject=str(spec["subject"])
        )
    return records


def annotation_record(trace_record: dict[str, object]) -> dict[str, object]:
    """Convert one saved generation into an unreviewed annotation record."""
    if trace_record.get("status") != "completed":
        raise ValueError("Only completed generations can enter the annotation queue.")
    problem = str(trace_record["problem"])
    steps = list(trace_record.get("initial_steps") or [])
    graph = trace_record.get("reasoning_graph")
    trace = graph if isinstance(graph, list) and graph else trace_nodes(problem, steps)
    benchmark_id = str(trace_record["benchmark_id"])
    return {
        "example_id": f"math500-{benchmark_id}",
        "source": "model_generated",
        "benchmark_id": benchmark_id,
        "model": str(trace_record.get("model", "")),
        "subject": str(trace_record.get("subject", "")),
        "level": trace_record.get("level"),
        "problem": problem,
        "trace": trace,
        "sampling_answer_correct": bool(trace_record.get("final_answer_correct")),
        "label_status": LABEL_UNREVIEWED,
        "trace_validity": None,
        "error_location": None,
        "error_type": None,
        "recovery_action": None,
    }


def apply_rescored_answers(
    records: dict[str, dict[str, object]],
    report: dict[str, object],
) -> dict[str, dict[str, object]]:
    """Use the published rescored answer flags when a report is available."""
    results = report.get("results")
    if not isinstance(results, list):
        return records
    updated = {key: dict(value) for key, value in records.items()}
    for item in results:
        if not isinstance(item, dict):
            continue
        benchmark_id = str(item.get("benchmark_id", ""))
        if benchmark_id in updated and "final_answer_correct" in item:
            updated[benchmark_id]["final_answer_correct"] = bool(
                item["final_answer_correct"]
            )
    return updated


def build_annotation_queue(
    records: dict[str, dict[str, object]],
) -> list[dict[str, object]]:
    """Keep completed traces and leave their supervision labels empty."""
    queue = [
        annotation_record(records[benchmark_id])
        for benchmark_id in sorted(records)
        if records[benchmark_id].get("status") == "completed"
    ]
    for index, example in enumerate(queue, start=1):
        validate_example(example, index=index)
    return queue


def apply_reviews(
    queue: list[dict[str, object]],
    reviews: list[dict[str, object]],
) -> list[dict[str, object]]:
    """Attach reviewed labels without copying reference answers into the queue."""
    by_id = {str(item["benchmark_id"]): dict(item) for item in queue}
    for review in reviews:
        benchmark_id = str(review["benchmark_id"])
        if benchmark_id not in by_id:
            raise ValueError(f"Review does not match a queued trace: {benchmark_id}")
        example = by_id[benchmark_id]
        example["label_status"] = LABEL_REVIEWED
        example["trace_validity"] = review["trace_validity"]
        example["error_location"] = review["error_location"]
        example["error_type"] = review["error_type"]
        example["recovery_action"] = review["recovery_action"]
        if review.get("annotation_note"):
            example["annotation_note"] = str(review["annotation_note"])
    reviewed_queue = [by_id[str(item["benchmark_id"])] for item in queue]
    for index, example in enumerate(reviewed_queue, start=1):
        validate_example(example, index=index)
    return reviewed_queue


def dataset_statistics(
    records: dict[str, dict[str, object]],
    queue: list[dict[str, object]],
) -> dict[str, object]:
    """Summarize the queue without treating answer correctness as a trace label."""
    reviewed = [item for item in queue if item["label_status"] == LABEL_REVIEWED]
    type_counts = Counter(str(item["error_type"]) for item in reviewed)
    required_types = (VALID_NO_REPAIR, *ERROR_TYPE_CODES)
    return {
        "saved_generations": len(records),
        "completed_traces": len(queue),
        "output_failures": sum(
            1 for record in records.values() if record.get("status") != "completed"
        ),
        "sampling_answer_correct": sum(
            1 for item in queue if item["sampling_answer_correct"]
        ),
        "sampling_answer_incorrect": sum(
            1 for item in queue if not item["sampling_answer_correct"]
        ),
        "reviewed_count": len(reviewed),
        "unreviewed_count": len(queue) - len(reviewed),
        "trace_validity_counts": dict(
            Counter(str(item["trace_validity"]) for item in reviewed)
        ),
        "error_type_counts": dict(type_counts),
        "recovery_action_counts": dict(
            Counter(str(item["recovery_action"]) for item in reviewed)
        ),
        "unobserved_error_types": [
            code for code in ERROR_TYPE_CODES if type_counts.get(code, 0) == 0
        ],
        "trainable": all(type_counts.get(code, 0) >= 3 for code in required_types),
        "note": (
            "Unreviewed rows are an annotation queue. sampling_answer_correct "
            "is not a trace-validity label and must not be used as VALID_NO_REPAIR."
        ),
    }


def write_dataset(
    queue: list[dict[str, object]],
    statistics: dict[str, object],
    output_path: Path,
    statistics_path: Path,
) -> None:
    output_path.write_text(
        json.dumps(queue, indent=2, ensure_ascii=True) + "\n", encoding="utf-8"
    )
    statistics_path.write_text(
        json.dumps(statistics, indent=2, ensure_ascii=True) + "\n", encoding="utf-8"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--traces", type=Path, default=DEFAULT_TRACES)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--reviews", type=Path, default=DEFAULT_REVIEWS)
    parser.add_argument("--statistics", type=Path, default=DEFAULT_STATISTICS)
    args = parser.parse_args()
    records = load_checkpoint(args.traces)
    if args.report.exists():
        report = json.loads(args.report.read_text(encoding="utf-8"))
        records = apply_rescored_answers(records, report)
    records.update(load_supplemental_equation_traces())
    records.update(load_checkpoint_supplements())
    queue = build_annotation_queue(records)
    if args.reviews.exists():
        reviews = json.loads(args.reviews.read_text(encoding="utf-8"))
        queue = apply_reviews(queue, reviews)
    statistics = dataset_statistics(records, queue)
    write_dataset(queue, statistics, args.output, args.statistics)
    print(
        f"Completed traces: {statistics['completed_traces']}; "
        f"unreviewed: {statistics['unreviewed_count']}"
    )
    print(f"Queue: {args.output}")
    print(f"Statistics: {args.statistics}")


if __name__ == "__main__":
    main()
