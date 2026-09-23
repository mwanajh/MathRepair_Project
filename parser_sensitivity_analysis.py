"""Re-evaluate saved model failures after parser-only normalization."""

import argparse
from collections import Counter
import json
from pathlib import Path
import re
from tokenize import TokenError

from collect_model_traces import answers_match
from mathrepair_demo import parse_equation
from model_pipeline import normalize_latex_equation, select_model_answer_step
from model_repair import has_isolated_answer
from reasoning_chain import analyze_chain


NORMALIZED_PARSER_VERSION = "offline_parser_normalization_v1"


def load_tolerant_steps(raw_response: str) -> list[str]:
    """Load a model steps array while repairing unescaped LaTeX commands."""
    repaired = re.sub(
        r"(?<!\\)\\(?=(?:frac|sqrt|left|right|cdot|times)\b)",
        r"\\\\",
        raw_response,
    )
    data = json.loads(repaired)
    steps = data.get("steps") if isinstance(data, dict) else None
    if not isinstance(steps, list) or not steps:
        raise ValueError("Raw response has no non-empty steps list.")
    if not all(isinstance(step, str) and step.strip() for step in steps):
        raise ValueError("Raw response contains an invalid step value.")
    return [step.strip() for step in steps]


def normalize_sensitivity_equation(text: str) -> str:
    """Normalize common model formatting without changing its arithmetic."""
    equation = text.strip()
    if ":" in equation and "=" not in equation.split(":", maxsplit=1)[0]:
        equation = equation.rsplit(":", maxsplit=1)[-1].strip()
    equation = re.sub(
        r"\\sqrt\[([^\]]+)\]\{([^{}]+)\}",
        r"((\2)^(1/(\1)))",
        equation,
    )
    equation = re.sub(r"\\sqrt\{([^{}]+)\}", r"sqrt(\1)", equation)
    equation = normalize_latex_equation(equation)
    equation = re.sub(r"\b0(?=[A-Za-z])", "0*", equation)
    return equation


def equation_fragments(step: str) -> list[str]:
    """Split alternatives and chained equalities into one-equality fragments."""
    fragments: list[str] = []
    for alternative in re.split(r"\s+or\s+", step, flags=re.IGNORECASE):
        parts = [part.strip() for part in alternative.split("=")]
        if len(parts) < 2:
            fragments.append(alternative.strip())
            continue
        fragments.extend(
            f"{left} = {right}"
            for left, right in zip(parts, parts[1:])
            if left and right
        )
    return fragments


def recover_failed_trace(
    problem: str, expected_answer: str, raw_response: str
) -> dict[str, object]:
    """Normalize one failed raw output and evaluate any recovered equations."""
    allowed_symbols = {
        str(symbol)
        for symbol in (
            parse_equation(problem).lhs.free_symbols
            | parse_equation(problem).rhs.free_symbols
        )
    }
    try:
        raw_steps = load_tolerant_steps(raw_response)
    except (json.JSONDecodeError, ValueError, TypeError) as error:
        return {
            "recovered": False,
            "steps": [],
            "discarded_steps": [],
            "trace_valid": False,
            "answer_correct": False,
            "has_isolated_answer": False,
            "first_error_node": None,
            "error_type": "unrecoverable_response_format",
            "failure": str(error),
        }
    recovered_steps: list[str] = []
    discarded: list[dict[str, str]] = []
    for raw_step in raw_steps:
        normalized = normalize_sensitivity_equation(raw_step)
        for fragment in equation_fragments(normalized):
            if fragment.count("=") != 1:
                discarded.append({"step": raw_step, "reason": "not_one_equation"})
                continue
            try:
                parsed = parse_equation(fragment)
            except (
                ValueError,
                TypeError,
                SyntaxError,
                TokenError,
                IndexError,
            ) as error:
                discarded.append(
                    {"step": raw_step, "reason": f"parse_error: {error}"}
                )
                continue
            symbols = {
                str(symbol)
                for symbol in parsed.lhs.free_symbols | parsed.rhs.free_symbols
            }
            if not symbols.issubset(allowed_symbols):
                discarded.append(
                    {"step": raw_step, "reason": "unsupported_extra_symbol"}
                )
                continue
            if fragment not in recovered_steps:
                recovered_steps.append(fragment)

    if not recovered_steps:
        return {
            "recovered": False,
            "steps": [],
            "discarded_steps": discarded,
            "trace_valid": False,
            "answer_correct": False,
            "has_isolated_answer": False,
            "first_error_node": None,
            "error_type": "parser_failure",
        }

    try:
        analysis = analyze_chain(problem, recovered_steps)
        answer_step = select_model_answer_step(problem, recovered_steps)
        answer_correct = answers_match(expected_answer, answer_step)
        isolated = has_isolated_answer(problem, recovered_steps)
        return {
            "recovered": True,
            "steps": recovered_steps,
            "discarded_steps": discarded,
            "trace_valid": analysis.error_node_id is None,
            "answer_step": answer_step,
            "answer_correct": answer_correct,
            "has_isolated_answer": isolated,
            "first_error_node": analysis.error_node_id,
            "error_type": analysis.error_type,
        }
    except (
        ValueError,
        TypeError,
        SyntaxError,
        TokenError,
        IndexError,
    ) as error:
        return {
            "recovered": False,
            "steps": recovered_steps,
            "discarded_steps": discarded,
            "trace_valid": False,
            "answer_correct": False,
            "has_isolated_answer": False,
            "first_error_node": None,
            "error_type": "normalized_verifier_failure",
            "failure": str(error),
        }


def analyze_directory(input_dir: Path) -> dict[str, object]:
    """Build sensitivity metrics from repeated-experiment trial folders."""
    trial_results: list[dict[str, object]] = []
    recovered_records: list[dict[str, object]] = []
    for trial_dir in sorted(input_dir.glob("seed_*")):
        report_path = trial_dir / "repair_report.json"
        trace_path = trial_dir / "traces.jsonl"
        if not report_path.exists() or not trace_path.exists():
            continue
        report = json.loads(report_path.read_text(encoding="utf-8"))
        failed_traces = []
        for line in trace_path.read_text(encoding="utf-8").splitlines():
            record = json.loads(line)
            if record.get("status") == "failed":
                failed_traces.append(record)

        recovered_answer_count = 0
        recovered_trace_count = 0
        recovered_output_count = 0
        isolated_answer_count = 0
        for failed in failed_traces:
            expected_answer = str(failed.get("labels", {}).get("expected_answer", ""))
            recovery = recover_failed_trace(
                str(failed["problem"]),
                expected_answer,
                str(failed.get("raw_response", "")),
            )
            output = {
                "trial": trial_dir.name,
                "problem": failed["problem"],
                "seed": int(failed.get("labels", {}).get("seed", 0)),
                "strict_failure": failed.get("failure", ""),
                **recovery,
            }
            recovered_records.append(output)
            recovered_output_count += int(bool(recovery["recovered"]))
            recovered_answer_count += int(bool(recovery["answer_correct"]))
            recovered_trace_count += int(bool(recovery["trace_valid"]))
            isolated_answer_count += int(bool(recovery["has_isolated_answer"]))

        run_count = int(report["run_count"])
        strict_answer_count = int(report["answer_correct_count"])
        strict_trace_count = int(report["trace_valid_count"])
        trial_results.append(
            {
                "base_seed": int(report["base_seed"]),
                "run_count": run_count,
                "strict_failure_count": int(report["failure_count"]),
                "recovered_output_count": recovered_output_count,
                "recovered_isolated_answer_count": isolated_answer_count,
                "recovered_answer_correct_count": recovered_answer_count,
                "recovered_trace_valid_count": recovered_trace_count,
                "strict_answer_accuracy": strict_answer_count / run_count,
                "normalized_answer_accuracy": (
                    strict_answer_count + recovered_answer_count
                )
                / run_count,
                "strict_trace_valid_rate": strict_trace_count / run_count,
                "normalized_trace_valid_rate": (
                    strict_trace_count + recovered_trace_count
                )
                / run_count,
            }
        )

    if not trial_results:
        raise ValueError(f"No trial reports found in {input_dir}.")
    total_runs = sum(int(item["run_count"]) for item in trial_results)
    failure_count = sum(int(item["strict_failure_count"]) for item in trial_results)
    recovered_count = sum(
        int(item["recovered_output_count"]) for item in trial_results
    )
    error_types = Counter(
        str(item["error_type"])
        for item in recovered_records
        if item.get("error_type")
    )
    return {
        "analysis": "parser_normalized_sensitivity",
        "parser_version": NORMALIZED_PARSER_VERSION,
        "input_directory": str(input_dir),
        "trial_count": len(trial_results),
        "total_runs": total_runs,
        "strict_failure_count": failure_count,
        "recovered_output_count": recovered_count,
        "unrecovered_output_count": failure_count - recovered_count,
        "recovered_answer_correct_count": sum(
            int(item["recovered_answer_correct_count"]) for item in trial_results
        ),
        "recovered_trace_valid_count": sum(
            int(item["recovered_trace_valid_count"]) for item in trial_results
        ),
        "recovered_isolated_answer_count": sum(
            int(item["recovered_isolated_answer_count"]) for item in trial_results
        ),
        "mean_strict_answer_accuracy": sum(
            float(item["strict_answer_accuracy"]) for item in trial_results
        )
        / len(trial_results),
        "mean_normalized_answer_accuracy": sum(
            float(item["normalized_answer_accuracy"]) for item in trial_results
        )
        / len(trial_results),
        "mean_strict_trace_valid_rate": sum(
            float(item["strict_trace_valid_rate"]) for item in trial_results
        )
        / len(trial_results),
        "mean_normalized_trace_valid_rate": sum(
            float(item["normalized_trace_valid_rate"]) for item in trial_results
        )
        / len(trial_results),
        "normalized_error_type_counts": dict(error_types),
        "trial_results": trial_results,
        "recovered_records": recovered_records,
        "caveat": (
            "This offline sensitivity analysis changes parser handling only. "
            "It does not replace the primary end-to-end comparison."
        ),
    }


def percent(value: float) -> str:
    return f"{100 * value:.1f}%"


def percentage_points(value: float) -> str:
    return f"{100 * value:+.1f} pp"


def render_markdown(report: dict[str, object]) -> str:
    return "\n".join(
        [
            "# Parser-Normalized Sensitivity Analysis",
            "",
            f"Trials: `{report['trial_count']}` | Runs: `{report['total_runs']}`",
            (
                f"Strict failures: `{report['strict_failure_count']}` | "
                f"Recovered outputs: `{report['recovered_output_count']}` | "
                f"Unrecovered: `{report['unrecovered_output_count']}`"
            ),
            (
                "Recovered outputs with isolated answers: "
                f"`{report['recovered_isolated_answer_count']}`"
            ),
            "",
            "| Metric | Strict pipeline | Parser-normalized | Difference |",
            "|---|---:|---:|---:|",
            (
                "| Answer accuracy | "
                f"{percent(report['mean_strict_answer_accuracy'])} | "
                f"{percent(report['mean_normalized_answer_accuracy'])} | "
                f"{percentage_points(report['mean_normalized_answer_accuracy'] - report['mean_strict_answer_accuracy'])} |"
            ),
            (
                "| Valid traces | "
                f"{percent(report['mean_strict_trace_valid_rate'])} | "
                f"{percent(report['mean_normalized_trace_valid_rate'])} | "
                f"{percentage_points(report['mean_normalized_trace_valid_rate'] - report['mean_strict_trace_valid_rate'])} |"
            ),
            "",
            (
                "Recovered correct answers: "
                f"`{report['recovered_answer_correct_count']}` | "
                "Recovered valid traces: "
                f"`{report['recovered_trace_valid_count']}`"
            ),
            "",
            f"Caveat: {report['caveat']}",
            "",
        ]
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--markdown", type=Path)
    args = parser.parse_args()
    output = args.output or args.input_dir / "parser_sensitivity_report.json"
    markdown = args.markdown or args.input_dir / "parser_sensitivity_report.md"
    report = analyze_directory(args.input_dir)
    output.write_text(
        json.dumps(report, indent=2, ensure_ascii=True) + "\n", encoding="utf-8"
    )
    markdown.write_text(render_markdown(report), encoding="utf-8")
    print(f"JSON: {output}")
    print(f"Markdown: {markdown}")


if __name__ == "__main__":
    main()
