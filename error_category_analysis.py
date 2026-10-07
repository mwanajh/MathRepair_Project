"""Compare local repair and global regeneration by detected error category."""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path


DEFAULT_MATCHED_REPORT = Path(__file__).with_name("matched_budget_report.json")
DEFAULT_SOURCE_REPORT = Path(__file__).with_name("stress_multisample_report.json")
DEFAULT_OUTPUT = Path(__file__).with_name("error_category_analysis.json")
DEFAULT_MARKDOWN = Path(__file__).with_name("error_category_analysis.md")
DEFAULT_REVIEWS = Path(__file__).with_name("natural_error_reviews.json")
DEFAULT_REVIEWED_OUTPUT = Path(__file__).with_name("reviewed_error_category_analysis.json")

MINIMUM_CASES_FOR_A_STRATEGY = 3
ERROR_CATEGORIES = (
    "arithmetic_error",
    "algebraic_transformation_error",
    "missing_assumption",
    "dependency_error",
    "incomplete_solution",
    "sign_error",
    "logical_inference_error",
    "semantic_interpretation_error",
)


def _success(value: object) -> bool:
    return bool(value)


def _error_runs(source: dict[str, object]) -> dict[tuple[int, str], dict[str, object]]:
    results = source.get("results")
    if not isinstance(results, list):
        raise ValueError("Source report is missing results.")
    indexed: dict[tuple[int, str], dict[str, object]] = {}
    for item in results:
        if not isinstance(item, dict) or item.get("status") != "completed":
            continue
        if not item.get("first_error_node"):
            continue
        try:
            key = (int(item["seed"]), str(item["problem"]))
        except (KeyError, TypeError, ValueError) as error:
            raise ValueError("Error run is missing a valid seed/problem key.") from error
        indexed[key] = item
    return indexed


def _strategy_records(
    matched: dict[str, object], name: str
) -> dict[tuple[int, str], dict[str, object]]:
    strategies = matched.get("strategies")
    if not isinstance(strategies, list):
        raise ValueError("Matched report is missing strategies.")
    strategy = next((item for item in strategies if item.get("name") == name), None)
    if not isinstance(strategy, dict):
        raise ValueError(f"Matched report is missing strategy: {name}")
    records = strategy.get("budget_records")
    if not isinstance(records, list):
        raise ValueError(f"Strategy has no budget records: {name}")
    return {
        (int(item["seed"]), str(item["problem"])): item
        for item in records
        if isinstance(item, dict)
    }


def _global_records(matched: dict[str, object]) -> dict[tuple[int, str], dict[str, object]]:
    records = matched.get("global_regeneration_results")
    if not isinstance(records, list):
        raise ValueError("Matched report is missing global_regeneration_results.")
    return {
        (int(item["seed"]), str(item["problem"])): item
        for item in records
        if isinstance(item, dict)
    }


def _local_success(record: dict[str, object]) -> bool:
    """Count only an accepted, answer-correct local candidate as success."""
    if not _success(record.get("accepted")):
        return False
    attempts = record.get("attempts")
    if not isinstance(attempts, list):
        return False
    return any(
        _success(attempt.get("accepted")) and _success(attempt.get("candidate_answer_correct"))
        for attempt in attempts
        if isinstance(attempt, dict)
    )


def _global_success(record: dict[str, object]) -> bool:
    return _success(record.get("accepted")) and _success(
        record.get("post_global_answer_correct")
    )


def _rate(successes: int, cases: int) -> float | None:
    return successes / cases if cases else None


def _evidence_status(observed: int) -> str:
    """Keep a small cell from being read as a strategy result."""
    if observed <= 0:
        return "unobserved"
    if observed < MINIMUM_CASES_FOR_A_STRATEGY:
        return "sparse"
    return "counted"


def _outcome_interpretation(rows: list[dict[str, object]]) -> str:
    """Describe only categories large enough to compare."""
    sentences = []
    for row in rows:
        if row["evidence_status"] != "counted":
            continue
        strategy = row["best_observed_strategy"]
        if strategy:
            sentences.append(
                f"{row['error_category']} has {row['observed_error_runs']} runs; "
                f"the higher repair rate in this pilot is {strategy}."
            )
        else:
            sentences.append(
                f"{row['error_category']} has {row['observed_error_runs']} runs "
                "and no single higher strategy."
            )
    sparse = [str(row["error_category"]) for row in rows if row["evidence_status"] == "sparse"]
    unobserved = [
        str(row["error_category"]) for row in rows if row["evidence_status"] == "unobserved"
    ]
    if sparse:
        sentences.append(
            f"{', '.join(sparse)} have fewer than {MINIMUM_CASES_FOR_A_STRATEGY} runs, "
            "so no strategy is selected."
        )
    if unobserved:
        sentences.append(
            f"{', '.join(unobserved)} were not observed. An empty cell is not a repair result."
        )
    return " ".join(sentences)


def analyze_categories(
    matched: dict[str, object], source: dict[str, object]
) -> dict[str, object]:
    error_runs = _error_runs(source)
    global_records = _global_records(matched)
    uniform_records = _strategy_records(matched, "verified_local_repair_uniform")
    adaptive_records = _strategy_records(matched, "verified_local_repair_adaptive")

    rows: list[dict[str, object]] = []
    for category in ERROR_CATEGORIES:
        keys = [key for key, item in error_runs.items() if item.get("error_type") == category]
        global_successes = sum(_global_success(global_records[key]) for key in keys if key in global_records)
        uniform_successes = sum(_local_success(uniform_records[key]) for key in keys if key in uniform_records)
        adaptive_successes = sum(_local_success(adaptive_records[key]) for key in keys if key in adaptive_records)
        observed = len(keys)
        rates = {
            "global_regeneration": _rate(global_successes, observed),
            "uniform_local_repair": _rate(uniform_successes, observed),
            "adaptive_local_repair": _rate(adaptive_successes, observed),
        }
        available = {name: value for name, value in rates.items() if value is not None}
        best_rate = max(available.values()) if available else None
        winners = [name for name, value in available.items() if value == best_rate] if best_rate is not None else []
        status = _evidence_status(observed)
        if status == "counted" and len(winners) == 1:
            best = winners[0]
        elif status == "counted" and len(winners) > 1:
            best = "tie"
        else:
            best = None
            winners = []
        rows.append(
            {
                "error_category": category,
                "observed_error_runs": observed,
                "global_success_count": global_successes,
                "global_success_rate": rates["global_regeneration"],
                "uniform_local_success_count": uniform_successes,
                "uniform_local_success_rate": rates["uniform_local_repair"],
                "adaptive_local_success_count": adaptive_successes,
                "adaptive_local_success_rate": rates["adaptive_local_repair"],
                "best_observed_strategy": best,
                "best_observed_strategies": winners,
                "evidence_status": status,
                "keys": [
                    {"seed": key[0], "problem": key[1]} for key in sorted(keys)
                ],
            }
        )

    observed_rows = [row for row in rows if row["observed_error_runs"]]
    return {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "experiment": "matched_budget_error_category_analysis",
        "source_matched_report": "matched_budget_report.json",
        "source_error_labels": "stress_multisample_report.json",
        "detected_error_run_count": len(error_runs),
        "observed_category_counts": dict(
            Counter(str(item.get("error_type")) for item in error_runs.values())
        ),
        "comparison_unit": "accepted answer-correct repair among detected-error runs",
        "rows": rows,
        "observed_categories": [row["error_category"] for row in observed_rows],
        "unobserved_categories": [
            row["error_category"] for row in rows if not row["observed_error_runs"]
        ],
        "sparse_categories": [
            row["error_category"] for row in rows if row["evidence_status"] == "sparse"
        ],
        "interpretation": _outcome_interpretation(rows),
        "limitations": [
            "Only seven detected-error runs are available.",
            "Five of the seven runs are algebraic-transformation errors.",
            "Rates describe this matched-budget pilot, not general error-type behavior.",
            "A strategy is named only when a category has at least three detected-error runs.",
            "Unobserved categories are not evidence of zero repair success.",
        ],
    }


def analyze_reviewed_error_categories(
    reviews: list[dict[str, object]],
) -> dict[str, object]:
    """Count reviewed recovery labels without turning a small cell into a strategy."""
    from error_taxonomy import ERROR_TYPE_CODES, VALID_NO_REPAIR
    from natural_error_dataset import RECOVERY_ACTIONS

    error_types = (VALID_NO_REPAIR, *ERROR_TYPE_CODES)
    rows: list[dict[str, object]] = []
    for error_type in error_types:
        group = [item for item in reviews if item.get("error_type") == error_type]
        counts = Counter(str(item.get("recovery_action")) for item in group)
        observed = len(group)
        status = _evidence_status(observed)
        unanimous = None
        if status == "counted":
            leaders = [action for action, count in counts.items() if count == observed]
            unanimous = leaders[0] if len(leaders) == 1 else None
        rows.append(
            {
                "error_type": error_type,
                "reviewed_count": observed,
                "recovery_action_counts": {
                    action: int(counts.get(action, 0)) for action in RECOVERY_ACTIONS
                },
                "evidence_status": status,
                "unanimous_reviewed_action": unanimous,
                "measured_repair_outcome": None,
            }
        )
    action_totals = Counter(
        str(item.get("recovery_action"))
        for item in reviews
        if isinstance(item, dict)
    )
    return {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "experiment": "reviewed_error_category_labels",
        "minimum_cases_for_a_named_action": MINIMUM_CASES_FOR_A_STRATEGY,
        "reviewed_count": len(reviews),
        "rows": rows,
        "unobserved_error_types": [
            row["error_type"] for row in rows if row["evidence_status"] == "unobserved"
        ],
        "sparse_error_types": [
            row["error_type"] for row in rows if row["evidence_status"] == "sparse"
        ],
        "unobserved_recovery_actions": [
            action for action in RECOVERY_ACTIONS if action_totals[action] == 0
        ],
        "interpretation": _reviewed_interpretation(rows),
        "limitations": [
            "Counts are reviewed labels, not measured repair outcomes.",
            "A zero recovery count means that action was not assigned. It is not a measured failure.",
            "A named action is the unanimous review in a category with at least three examples.",
            "GLOBAL_REGENERATE remains unobserved. That empty cell is not evidence against global regeneration.",
        ],
    }


def _reviewed_interpretation(rows: list[dict[str, object]]) -> str:
    sentences = []
    for row in rows:
        action = row["unanimous_reviewed_action"]
        if row["evidence_status"] == "counted" and action:
            sentences.append(
                f"{row['error_type']} has {row['reviewed_count']} reviews, all labeled {action}."
            )
        elif row["evidence_status"] == "counted":
            sentences.append(
                f"{row['error_type']} has {row['reviewed_count']} reviews and more than one recovery label, so no single action is selected."
            )
    sparse = [str(row["error_type"]) for row in rows if row["evidence_status"] == "sparse"]
    unobserved = [str(row["error_type"]) for row in rows if row["evidence_status"] == "unobserved"]
    if sparse:
        sentences.append(
            f"{', '.join(sparse)} have fewer than {MINIMUM_CASES_FOR_A_STRATEGY} reviews, so no action is selected."
        )
    if unobserved:
        sentences.append(
            f"{', '.join(unobserved)} were not observed. An empty error type is not a repair result."
        )
    sentences.append("These labels do not measure whether the named action repairs the answer.")
    return " ".join(sentences)


def _percent(value: object) -> str:
    return "--" if value is None else f"{100 * float(value):.1f}%"


def render_markdown(report: dict[str, object]) -> str:
    lines = [
        "# Error-Category Repair Analysis",
        "",
        f"Detected error runs: {report['detected_error_run_count']}",
        "",
        "| Error category | Cases | Global regeneration | Uniform local | Adaptive local | Best observed | Evidence |",
        "|---|---:|---:|---:|---:|---|---|",
    ]
    for row in report["rows"]:
        lines.append(
            f"| {row['error_category']} | {row['observed_error_runs']} | "
            f"{row['global_success_count']}/{row['observed_error_runs']} ({_percent(row['global_success_rate'])}) | "
            f"{row['uniform_local_success_count']}/{row['observed_error_runs']} ({_percent(row['uniform_local_success_rate'])}) | "
            f"{row['adaptive_local_success_count']}/{row['observed_error_runs']} ({_percent(row['adaptive_local_success_rate'])}) | "
            f"{row['best_observed_strategy'] or '--'} | {row['evidence_status']} |"
        )
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            report["interpretation"],
            "",
            "## Limitations",
            "",
        ]
    )
    lines.extend(f"- {item}" for item in report["limitations"])
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--matched-report", type=Path, default=DEFAULT_MATCHED_REPORT)
    parser.add_argument("--source-report", type=Path, default=DEFAULT_SOURCE_REPORT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--markdown", type=Path, default=DEFAULT_MARKDOWN)
    parser.add_argument("--reviews", type=Path, default=DEFAULT_REVIEWS)
    parser.add_argument("--reviewed-output", type=Path, default=DEFAULT_REVIEWED_OUTPUT)
    args = parser.parse_args()
    try:
        report = analyze_categories(
            json.loads(args.matched_report.read_text(encoding="utf-8")),
            json.loads(args.source_report.read_text(encoding="utf-8")),
        )
        args.output.write_text(
            json.dumps(report, indent=2, ensure_ascii=True) + "\n", encoding="utf-8"
        )
        args.markdown.write_text(render_markdown(report), encoding="utf-8")
        reviews = json.loads(args.reviews.read_text(encoding="utf-8"))
        reviewed = analyze_reviewed_error_categories(reviews)
        args.reviewed_output.write_text(
            json.dumps(reviewed, indent=2, ensure_ascii=True) + "\n", encoding="utf-8"
        )
    except (OSError, ValueError, TypeError, KeyError) as error:
        parser.error(str(error))
    for row in report["rows"]:
        print(
            f"{row['error_category']}: cases={row['observed_error_runs']}, "
            f"global={_percent(row['global_success_rate'])}, "
            f"adaptive={_percent(row['adaptive_local_success_rate'])}, "
            f"best={row['best_observed_strategy'] or '--'}"
        )
    print(f"JSON: {args.output}")
    print(f"Markdown: {args.markdown}")


if __name__ == "__main__":
    main()
