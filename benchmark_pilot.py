"""Smoke-run the model pipeline on the MATH-500 hard pilot subset."""

import argparse
import json
from pathlib import Path

from model_pipeline import OllamaMathModel, PipelineResult, run_pipeline, save_trace


DEFAULT_PROBLEMS = Path(__file__).with_name("math500_pilot_40.json")
DEFAULT_TRACES = Path(__file__).with_name("math500_pilot_traces.jsonl")
DEFAULT_RESULTS = Path(__file__).with_name("math500_pilot_run.json")


class PilotMockModel:
    """Offline smoke model used to validate the text-mode pipeline contract."""

    def __init__(self, answer: str) -> None:
        self.answer = answer
        self.last_raw_response = json.dumps(
            {"steps": ["Parse the problem statement", f"Answer: {answer}"]}
        )
        self.last_metadata = {"problem_format": "text", "offline": "true"}

    def solve(self, problem: str) -> list[str]:
        return ["Parse the problem statement", f"Answer: {self.answer}"]


def load_pilot(path: Path, limit: int | None) -> list[dict[str, object]]:
    """Load and validate the JSONL pilot records."""
    raw = path.read_text(encoding="utf-8")
    try:
        decoded = json.loads(raw)
    except json.JSONDecodeError:
        decoded = []
        for line_number, line in enumerate(raw.splitlines(), start=1):
            try:
                decoded.append(json.loads(line))
            except json.JSONDecodeError as error:
                raise ValueError(f"Invalid JSON at line {line_number}.") from error
    records = []
    for record in decoded:
        required = {"benchmark_id", "problem", "answer", "subject", "level"}
        if not isinstance(record, dict) or not required.issubset(record):
            raise ValueError(f"Pilot record at line {line_number} is incomplete.")
        if int(record["level"]) < 4:
            raise ValueError(f"Pilot record at line {line_number} is not level 4-5.")
        records.append(record)
    if not records:
        raise ValueError("Pilot file contains no records.")
    return records[:limit] if limit is not None else records


def run_pilot(
    problems: list[dict[str, object]],
    provider: str,
    model_name: str,
    traces: Path,
) -> list[dict[str, object]]:
    """Process each record through the text-mode model and graph pipeline."""
    traces.write_text("", encoding="utf-8")
    results: list[dict[str, object]] = []
    for record in problems:
        if provider == "ollama":
            model = OllamaMathModel(model_name, problem_format="text")
        else:
            model = PilotMockModel(str(record["answer"]))
        result: PipelineResult = run_pipeline(
            str(record["problem"]),
            model,
            provider=provider,
            model_name=model_name,
            model_repair_attempts=0,
        )
        save_trace(
            traces,
            result,
            labels={
                "benchmark": str(record.get("benchmark", "MATH-500")),
                "benchmark_id": str(record["benchmark_id"]),
                "subject": str(record["subject"]),
                "level": str(record["level"]),
                "reference_answer": str(record["answer"]),
            },
        )
        results.append(
            {
                "benchmark_id": record["benchmark_id"],
                "subject": record["subject"],
                "level": record["level"],
                "step_count": len(result.steps),
                "verification_mode": result.analysis.verification_mode,
                "graph_node_count": len(result.reasoning_graph),
                "processed": True,
            }
        )
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--problems", type=Path, default=DEFAULT_PROBLEMS)
    parser.add_argument("--traces", type=Path, default=DEFAULT_TRACES)
    parser.add_argument("--results", type=Path, default=DEFAULT_RESULTS)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--provider", choices=["mock", "ollama"], default="mock")
    parser.add_argument("--model", default="qwen2-math:1.5b")
    args = parser.parse_args()

    if args.limit is not None and args.limit < 1:
        parser.error("--limit must be at least 1.")
    try:
        problems = load_pilot(args.problems, args.limit)
        results = run_pilot(problems, args.provider, args.model, args.traces)
        args.results.write_text(
            json.dumps(
                {
                    "benchmark": "MATH-500",
                    "provider": args.provider,
                    "model": args.model,
                    "problem_count": len(results),
                    "verification_mode": "text_unverified",
                    "results": results,
                },
                indent=2,
                ensure_ascii=True,
            )
            + "\n",
            encoding="utf-8",
        )
    except (OSError, ValueError, TypeError, SyntaxError) as error:
        parser.error(str(error))
    print(f"Processed {len(results)} pilot problems with {args.provider} provider.")
    print(f"Traces: {args.traces}")
    print(f"Results: {args.results}")


if __name__ == "__main__":
    main()
