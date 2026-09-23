"""Build the planned MathRepair ablation matrix from measured artifacts."""

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path


DEFAULT_MATCHED_REPORT = Path(__file__).with_name("matched_budget_report.json")
DEFAULT_OUTPUT = Path(__file__).with_name("ablation_table.json")
DEFAULT_MARKDOWN = Path(__file__).with_name("ablation_table.md")


METRIC_KEYS = (
    "answer_accuracy",
    "trace_valid_rate",
    "repair_success_rate",
    "average_model_calls",
    "average_tokens",
    "total_compute_cost",
)


def strategy_by_name(
    report: dict[str, object], name: str
) -> dict[str, object]:
    """Return one named matched-budget strategy or fail explicitly."""
    strategies = report.get("strategies")
    if not isinstance(strategies, list):
        raise ValueError("Matched-budget report must contain a strategy list.")
    for strategy in strategies:
        if not isinstance(strategy, dict):
            raise ValueError("Each matched-budget strategy must be an object.")
        if strategy.get("name") == name:
            return strategy
    raise ValueError(f"Matched-budget report is missing strategy: {name}")


def measured_metrics(strategy: dict[str, object]) -> dict[str, object]:
    """Copy the shared ablation metrics from a measured strategy."""
    missing = [key for key in METRIC_KEYS if key not in strategy]
    if missing:
        raise ValueError(f"Strategy is missing metrics: {', '.join(missing)}")
    return {key: strategy[key] for key in METRIC_KEYS}


def planned_metrics() -> dict[str, None]:
    """Return explicit null cells for an ablation not run yet."""
    return {key: None for key in METRIC_KEYS}


def build_ablation_table(
    matched_report: dict[str, object]
) -> dict[str, object]:
    """Create the frozen six-row ablation structure with honest result status."""
    if not matched_report.get("matched_budget_comparison_valid", False):
        raise ValueError("Matched-budget source report is not valid.")
    if matched_report.get("local_evaluation_mode") != "live":
        raise ValueError("Ablation metrics require fresh-call local results.")

    adaptive = strategy_by_name(
        matched_report, "verified_local_repair_adaptive"
    )
    uniform = strategy_by_name(
        matched_report, "verified_local_repair_uniform"
    )
    global_regeneration = strategy_by_name(
        matched_report, "verified_global_regeneration"
    )
    full_metrics = measured_metrics(adaptive)

    rows = [
        {
            "variant_id": "full_mathrepair",
            "variant": "Full MathRepair",
            "graph": "on",
            "typed_error": "rule_based_proxy",
            "adaptive_compute": "on",
            "repair_scope": "local",
            "symbolic_tool": "on",
            "status": "proxy_result",
            "result_source": "verified_local_repair_adaptive",
            "metrics": full_metrics,
            "delta_answer_accuracy_pp": 0.0,
            "note": (
                "Pipeline-complete proxy only; learned typed verifier is not "
                "trained yet."
            ),
        },
        {
            "variant_id": "no_graph",
            "variant": "No graph",
            "graph": "off",
            "typed_error": "rule_based_proxy",
            "adaptive_compute": "on",
            "repair_scope": "local",
            "symbolic_tool": "on",
            "status": "planned",
            "result_source": "",
            "metrics": planned_metrics(),
            "delta_answer_accuracy_pp": None,
            "note": "Flatten nodes into a sequence and disable dependency impact propagation.",
        },
        {
            "variant_id": "no_typed_error",
            "variant": "No typed error",
            "graph": "on",
            "typed_error": "off_binary_only",
            "adaptive_compute": "on",
            "repair_scope": "local",
            "symbolic_tool": "on",
            "status": "planned",
            "result_source": "",
            "metrics": planned_metrics(),
            "delta_answer_accuracy_pp": None,
            "note": "Use only valid/invalid labels and one generic local-resample action.",
        },
        {
            "variant_id": "no_adaptive_compute",
            "variant": "No adaptive compute",
            "graph": "on",
            "typed_error": "rule_based_proxy",
            "adaptive_compute": "off_uniform",
            "repair_scope": "local",
            "symbolic_tool": "on",
            "status": "measured",
            "result_source": "verified_local_repair_uniform",
            "metrics": measured_metrics(uniform),
            "delta_answer_accuracy_pp": 100
            * (
                float(uniform["answer_accuracy"])
                - float(adaptive["answer_accuracy"])
            ),
            "note": "Uses the fresh-call uniform arm from the matched-budget pilot.",
        },
        {
            "variant_id": "global_instead_of_local",
            "variant": "Global regeneration instead of local repair",
            "graph": "on",
            "typed_error": "rule_based_proxy",
            "adaptive_compute": "off_global",
            "repair_scope": "global",
            "symbolic_tool": "on",
            "status": "measured",
            "result_source": "verified_global_regeneration",
            "metrics": measured_metrics(global_regeneration),
            "delta_answer_accuracy_pp": 100
            * (
                float(global_regeneration["answer_accuracy"])
                - float(adaptive["answer_accuracy"])
            ),
            "note": "Uses the fresh-call global arm under the matched ceiling.",
        },
        {
            "variant_id": "no_symbolic_tool",
            "variant": "No symbolic tool",
            "graph": "on",
            "typed_error": "learned_pending",
            "adaptive_compute": "on",
            "repair_scope": "local",
            "symbolic_tool": "off",
            "status": "blocked_by_learned_verifier",
            "result_source": "",
            "metrics": planned_metrics(),
            "delta_answer_accuracy_pp": None,
            "note": "Requires the learned verifier before symbolic acceptance can be removed.",
        },
    ]

    source = matched_report.get("source")
    if not isinstance(source, dict):
        raise ValueError("Matched-budget report is missing source metadata.")
    return {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "table_status": "structure_frozen_partial_results",
        "primary_comparison_metric": "answer_accuracy",
        "source": {
            "artifact": "matched_budget_report.json",
            "model": source.get("model", ""),
            "run_count": source.get("run_count", 0),
            "detected_error_runs": source.get("detected_error_runs", 0),
            "matched_additional_token_budget": matched_report.get(
                "matched_additional_token_budget", 0
            ),
            "local_evaluation_mode": matched_report.get(
                "local_evaluation_mode", ""
            ),
        },
        "rows": rows,
        "completion": {
            "row_count": len(rows),
            "measured_count": sum(row["status"] == "measured" for row in rows),
            "proxy_count": sum(row["status"] == "proxy_result" for row in rows),
            "planned_count": sum(
                row["status"] not in {"measured", "proxy_result"} for row in rows
            ),
        },
        "interpretation_rule": (
            "Only rows marked measured may support an ablation claim. The full "
            "row is a rule-based proxy until the learned verifier is trained."
        ),
    }


def percent(value: object) -> str:
    return "--" if value is None else f"{100 * float(value):.1f}%"


def number(value: object, digits: int = 2) -> str:
    return "--" if value is None else f"{float(value):.{digits}f}"


def integer(value: object) -> str:
    return "--" if value is None else f"{int(value):,}"


def token_cost(value: object) -> str:
    return "--" if value is None else f"{integer(value)} tokens"


def render_markdown(report: dict[str, object]) -> str:
    """Render the paper-facing ablation table and experiment TODOs."""
    source = report["source"]
    lines = [
        "# MathRepair Ablation Table",
        "",
        (
            f"Model: `{source['model']}` | Runs: {source['run_count']} | "
            f"Detected errors: {source['detected_error_runs']} | "
            f"Matched additional-token ceiling: "
            f"{source['matched_additional_token_budget']:,}"
        ),
        "",
        (
            "| Variant | Graph | Typed error | Adaptive compute | Repair | "
            "Symbolic tool | Answer accuracy | Valid trace | Repair success | "
            "Avg calls | Avg tokens | Total cost | Status |"
        ),
        "|---|---|---|---|---|---|---:|---:|---:|---:|---:|---:|---|",
    ]
    for row in report["rows"]:
        metrics = row["metrics"]
        lines.append(
            f"| {row['variant']} | {row['graph']} | {row['typed_error']} | "
            f"{row['adaptive_compute']} | {row['repair_scope']} | "
            f"{row['symbolic_tool']} | {percent(metrics['answer_accuracy'])} | "
            f"{percent(metrics['trace_valid_rate'])} | "
            f"{percent(metrics['repair_success_rate'])} | "
            f"{number(metrics['average_model_calls'])} | "
            f"{number(metrics['average_tokens'], 1)} | "
            f"{token_cost(metrics['total_compute_cost'])} | {row['status']} |"
        )
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            f"{report['interpretation_rule']}",
            "",
            "The two measured ablations currently show:",
            "",
        ]
    )
    for row in report["rows"]:
        if row["status"] == "measured":
            lines.append(
                f"- {row['variant']}: answer-accuracy delta versus the full "
                f"proxy = {row['delta_answer_accuracy_pp']:+.1f} pp."
            )
    lines.extend(["", "## Remaining Runs", ""])
    for row in report["rows"]:
        if row["status"] not in {"measured", "proxy_result"}:
            lines.append(f"- {row['variant']}: {row['note']}")
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--matched-report", type=Path, default=DEFAULT_MATCHED_REPORT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--markdown", type=Path, default=DEFAULT_MARKDOWN)
    args = parser.parse_args()

    matched_report = json.loads(args.matched_report.read_text(encoding="utf-8"))
    report = build_ablation_table(matched_report)
    args.output.write_text(
        json.dumps(report, indent=2, ensure_ascii=True) + "\n", encoding="utf-8"
    )
    args.markdown.write_text(render_markdown(report), encoding="utf-8")
    print(
        f"Ablation rows: {report['completion']['row_count']} "
        f"(measured={report['completion']['measured_count']}, "
        f"proxy={report['completion']['proxy_count']}, "
        f"planned={report['completion']['planned_count']})"
    )
    print(f"JSON: {args.output}")
    print(f"Markdown: {args.markdown}")


if __name__ == "__main__":
    main()
