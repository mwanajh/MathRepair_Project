"""Connect a math model to the MathRepair verification pipeline."""

import argparse
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import re
from tokenize import TokenError
from typing import Protocol
from urllib import error as url_error
from urllib import request as url_request

from local_repair import LocalRepairResult, apply_local_repair
from model_repair import ModelRepairResult, attempt_model_repair
from reasoning_chain import ChainAnalysis, analyze_chain
from repair_policy import RepairDecision, make_repair_decision


class MathModel(Protocol):
    """A model that returns equation-only reasoning steps."""

    def solve(self, problem: str) -> list[str]:
        """Generate ordered solution steps for one problem."""


@dataclass
class PipelineResult:
    """Model output plus MathRepair's diagnosis and action."""

    problem: str
    provider: str
    model: str
    steps: list[str]
    analysis: ChainAnalysis
    decision: RepairDecision
    repair: LocalRepairResult
    model_repair: ModelRepairResult
    raw_response: str
    generation_metadata: dict[str, int | str]


class MockMathModel:
    """Offline model stub that deliberately produces one algebra error."""

    def solve(self, problem: str) -> list[str]:
        self.last_raw_response = ""
        self.last_metadata: dict[str, int | str] = {}
        if problem.replace(" ", "") == "2(x+3)=14":
            return ["2x + 3 = 14", "2x = 11", "x = 5.5"]
        return [problem]

    def repair(
        self,
        problem: str,
        valid_prefix: list[str],
        bad_step: str,
        error_type: str,
        attempt_index: int,
    ) -> list[str]:
        self.last_repair_raw_response = (
            '{"steps": ["2x + 6 = 14", "x = 4"]}'
        )
        self.last_repair_metadata: dict[str, int | float | str] = {
            "seed": attempt_index
        }
        return ["2x + 6 = 14", "x = 4"]


class OllamaMathModel:
    """Minimal client for an Ollama server running on this computer."""

    def __init__(
        self,
        model: str,
        base_url: str = "http://localhost:11434",
        timeout_seconds: int = 120,
        seed: int = 42,
        temperature: float = 0.0,
        max_output_tokens: int | None = None,
        prompt_profile: str = "default",
    ) -> None:
        if not model.strip():
            raise ValueError("Ollama model name cannot be empty.")
        if max_output_tokens is not None and max_output_tokens < 1:
            raise ValueError("max_output_tokens must be at least 1.")
        if prompt_profile not in {"default", "qwen2_math_json"}:
            raise ValueError(
                "prompt_profile must be 'default' or 'qwen2_math_json'."
            )
        self.model = model
        self.endpoint = f"{base_url.rstrip('/')}/api/generate"
        self.timeout_seconds = timeout_seconds
        self.seed = seed
        self.temperature = temperature
        self.max_output_tokens = max_output_tokens
        self.prompt_profile = prompt_profile
        self.last_raw_response = ""
        self.last_metadata: dict[str, int | str] = {}
        self.last_repair_raw_response = ""
        self.last_repair_metadata: dict[str, int | float | str] = {}

    def _generate_response(
        self, prompt: str, seed: int
    ) -> tuple[str, dict[str, int | float | str]]:
        options: dict[str, int | float] = {
            "temperature": self.temperature,
            "seed": seed,
        }
        if self.max_output_tokens is not None:
            options["num_predict"] = self.max_output_tokens
        payload = json.dumps(
            {
                "model": self.model,
                "prompt": prompt,
                "stream": False,
                "options": options,
                **(
                    {"format": "json"}
                    if self.prompt_profile == "qwen2_math_json"
                    else {}
                ),
            }
        ).encode("utf-8")
        request = url_request.Request(
            self.endpoint,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with url_request.urlopen(
                request, timeout=self.timeout_seconds
            ) as response:
                ollama_result = json.loads(response.read().decode("utf-8"))
        except url_error.HTTPError as error:
            details = error.read().decode("utf-8", errors="replace")
            raise ValueError(f"Ollama HTTP {error.code}: {details}") from error
        if "response" not in ollama_result:
            raise ValueError("Ollama response is missing the 'response' field.")
        raw_response = ollama_result["response"]
        metadata_fields = (
            "done_reason",
            "total_duration",
            "load_duration",
            "prompt_eval_count",
            "prompt_eval_duration",
            "eval_count",
            "eval_duration",
        )
        metadata: dict[str, int | float | str] = {
            field: ollama_result[field]
            for field in metadata_fields
            if field in ollama_result
        }
        metadata["seed"] = seed
        metadata["temperature"] = self.temperature
        metadata["prompt_profile"] = self.prompt_profile
        return raw_response, metadata

    def _parse_equation_response(self, problem: str, response: str) -> list[str]:
        if self.prompt_profile == "qwen2_math_json":
            return parse_qwen_json_steps(problem, response)
        try:
            return parse_model_steps(response)
        except ValueError:
            problem_equation = parse_problem_equation(problem)
            allowed_symbols = {
                str(symbol)
                for symbol in (
                    problem_equation.lhs.free_symbols
                    | problem_equation.rhs.free_symbols
                )
            }
            return extract_equation_steps(
                response,
                allowed_symbols=allowed_symbols,
            )

    def solve(self, problem: str) -> list[str]:
        if self.prompt_profile == "qwen2_math_json":
            prompt = (
                "Solve the equation. Output exactly one JSON object with one "
                "field named steps. steps must contain only complete equation "
                "strings, in order; do not put explanations, labels, or prose "
                "inside steps. Every string must contain exactly one '=' sign. "
                "Use plain ASCII math only: / for fractions, * for products, "
                "and ^ for powers. Do not use LaTeX, Markdown, code fences, or "
                "any text outside the JSON object.\n\n"
                f"Problem: {problem}"
            )
        else:
            prompt = (
                "Solve this equation step by step. Return only a JSON object with "
                "one field named steps. steps must be a non-empty array of strings. "
                "Every string must be a complete equation with exactly one '=' sign. "
                "Do not include prose or Markdown.\n\n"
                f"Problem: {problem}"
            )
        self.last_raw_response, self.last_metadata = self._generate_response(
            prompt, self.seed
        )
        return self._parse_equation_response(problem, self.last_raw_response)

    def repair(
        self,
        problem: str,
        valid_prefix: list[str],
        bad_step: str,
        error_type: str,
        attempt_index: int,
    ) -> list[str]:
        if error_type == "incomplete_solution":
            task = (
                "Continue from the final verified equation and isolate the "
                "problem variable. Do not repeat the verified prefix."
            )
            trigger_label = "Final verified equation"
        else:
            task = (
                "Replace the invalid step and continue until the problem "
                "variable is isolated."
            )
            trigger_label = "First invalid step"
        contract = (
            "Return exactly one JSON object with one field named steps. Put only "
            "complete plain-ASCII equations in steps, one '=' per string. Do not "
            "include prose, labels, LaTeX, Markdown, or code fences. "
            if self.prompt_profile == "qwen2_math_json"
            else "Return only a JSON object with one field named steps. steps must "
            "be a non-empty array of complete equations with exactly one '=' sign. "
            "Do not include prose or Markdown. "
        )
        prompt = (
            "Repair a mathematical reasoning chain locally. You are not given "
            "the correct answer. "
            f"{contract}{task}\n\n"
            f"Problem: {problem}\n"
            f"Verified prefix: {json.dumps(valid_prefix)}\n"
            f"{trigger_label}: {bad_step}\n"
            f"Diagnosed state: {error_type}"
        )
        repair_seed = self.seed + 100_000 + attempt_index
        (
            self.last_repair_raw_response,
            self.last_repair_metadata,
        ) = self._generate_response(prompt, repair_seed)
        return self._parse_equation_response(
            problem, self.last_repair_raw_response
        )


def parse_model_steps(response_text: str) -> list[str]:
    """Validate the model's strict JSON response."""
    try:
        data = json.loads(response_text)
    except json.JSONDecodeError as error:
        raise ValueError("Model did not return valid JSON.") from error

    steps = data.get("steps") if isinstance(data, dict) else None
    if not isinstance(steps, list) or not steps:
        raise ValueError("Model JSON must contain a non-empty 'steps' list.")
    if not all(isinstance(step, str) and step.strip() for step in steps):
        raise ValueError("Every model step must be a non-empty string.")
    if not all(step.count("=") == 1 for step in steps):
        raise ValueError("Every model step must be an equation with exactly one '=' sign.")
    return [step.strip() for step in steps]


def parse_qwen_json_steps(problem: str, response_text: str) -> list[str]:
    """Parse Qwen JSON while discarding explanatory entries in ``steps``.

    This parser is opt-in because dropping non-equation entries changes the
    strict output contract used by the primary evaluation.
    """
    candidate = response_text.strip()
    if candidate.startswith("```"):
        candidate = re.sub(r"^```(?:json)?\s*|\s*```$", "", candidate, flags=re.I | re.S)
    try:
        data = json.loads(candidate)
    except json.JSONDecodeError:
        start, end = candidate.find("{"), candidate.rfind("}")
        if start < 0 or end <= start:
            raise ValueError("Qwen response contains no readable JSON object.")
        try:
            data = json.loads(candidate[start : end + 1])
        except json.JSONDecodeError as error:
            raise ValueError("Qwen response does not contain a valid JSON object.") from error
    raw_steps = data.get("steps") if isinstance(data, dict) else None
    if not isinstance(raw_steps, list) or not raw_steps:
        raise ValueError("Qwen JSON must contain a non-empty 'steps' list.")
    equation = parse_problem_equation(problem)
    allowed_symbols = {
        str(symbol) for symbol in equation.lhs.free_symbols | equation.rhs.free_symbols
    }
    recovered: list[str] = []
    for item in raw_steps:
        if not isinstance(item, str) or not item.strip():
            continue
        normalized = normalize_latex_equation(item)
        if normalized.count("=") != 1:
            continue
        try:
            parsed = parse_problem_equation(normalized)
        except (ValueError, TypeError, SyntaxError, TokenError):
            continue
        symbols = {
            str(symbol) for symbol in parsed.lhs.free_symbols | parsed.rhs.free_symbols
        }
        if symbols.issubset(allowed_symbols) and normalized not in recovered:
            recovered.append(normalized)
    if not recovered:
        raise ValueError("Qwen response contains no readable equation steps.")
    return recovered


def normalize_latex_equation(text: str) -> str:
    """Convert a small, verifier-compatible subset of LaTeX to plain text."""
    equation = text.strip()
    equation = equation.replace("\\left", "").replace("\\right", "")
    equation = equation.replace("\\cdot", "*").replace("\\times", "*")
    fraction_pattern = re.compile(r"\\frac\{([^{}]+)\}\{([^{}]+)\}")
    while fraction_pattern.search(equation):
        equation = fraction_pattern.sub(r"(\1)/(\2)", equation)
    equation = re.sub(r"\^\{([^{}]+)\}", r"^\1", equation)
    equation = equation.replace("\\,", " ")
    equation = equation.strip(" $.,;:")
    return " ".join(equation.split())


def parse_problem_equation(problem: str):
    """Parse a problem without creating a module-level circular import."""
    from mathrepair_demo import parse_equation

    return parse_equation(problem)


def extract_equation_steps(
    response_text: str,
    allowed_symbols: set[str] | None = None,
) -> list[str]:
    """Extract parseable equations when a local model returns prose/LaTeX."""
    candidates: list[str] = []
    candidates.extend(re.findall(r"\\\[(.*?)\\\]", response_text, re.DOTALL))
    candidates.extend(re.findall(r"\\\((.*?)\\\)", response_text, re.DOTALL))
    candidates.extend(response_text.splitlines())

    steps: list[str] = []
    seen_steps: set[str] = set()
    for candidate in candidates:
        for fragment in re.split(r"\\\\|[\r\n]", candidate):
            equation = normalize_latex_equation(fragment)
            if equation.count("=") != 1:
                continue
            if any(marker in equation for marker in ("{\"", "steps", "text")):
                continue
            try:
                from mathrepair_demo import parse_equation

                parsed = parse_equation(equation)
            except (ValueError, TypeError, SyntaxError, TokenError):
                continue
            symbols = {
                str(symbol)
                for symbol in (
                    parsed.lhs.free_symbols | parsed.rhs.free_symbols
                )
            }
            if allowed_symbols is not None and not symbols.issubset(allowed_symbols):
                continue
            if equation not in seen_steps:
                steps.append(equation)
                seen_steps.add(equation)

    if not steps:
        raise ValueError("Model response contains no readable equation steps.")
    return steps


def select_model_answer_step(problem: str, steps: list[str]) -> str:
    """Prefer the last step that isolates a variable from the problem."""
    problem_equation = parse_problem_equation(problem)
    problem_symbols = (
        problem_equation.lhs.free_symbols | problem_equation.rhs.free_symbols
    )
    if not problem_symbols:
        return steps[-1]

    from mathrepair_demo import parse_equation

    parsed_steps = []
    for step in steps:
        equation = parse_equation(step)
        parsed_steps.append((step, equation))

    for step, equation in reversed(parsed_steps):
        if any(
            equation.lhs == symbol or equation.rhs == symbol
            for symbol in problem_symbols
        ):
            return step

    for step, equation in reversed(parsed_steps):
        step_symbols = equation.lhs.free_symbols | equation.rhs.free_symbols
        if step_symbols & problem_symbols:
            return step
    return steps[-1]


def run_pipeline(
    problem: str,
    model_client: MathModel,
    provider: str,
    model_name: str,
    model_repair_attempts: int = 1,
) -> PipelineResult:
    """Generate steps, diagnose the first error, and select a repair action."""
    steps = model_client.solve(problem)
    analysis = analyze_chain(problem, steps)
    decision = make_repair_decision(
        analysis.error_type, analysis.suggested_repair
    )
    repair = apply_local_repair(problem, steps, analysis)
    model_repair = attempt_model_repair(
        problem,
        steps,
        analysis,
        model_client,
        model_repair_attempts,
    )
    return PipelineResult(
        problem=problem,
        provider=provider,
        model=model_name,
        steps=steps,
        analysis=analysis,
        decision=decision,
        repair=repair,
        model_repair=model_repair,
        raw_response=getattr(model_client, "last_raw_response", ""),
        generation_metadata=getattr(model_client, "last_metadata", {}),
    )


def append_jsonl_record(path: Path, record: dict[str, object]) -> None:
    """Append one JSON object to a JSONL file."""
    with path.open("a", encoding="utf-8") as file:
        file.write(json.dumps(record, ensure_ascii=True) + "\n")


def save_trace(
    path: Path,
    result: PipelineResult,
    labels: dict[str, str] | None = None,
) -> None:
    """Append one model run as JSONL for later natural-error analysis."""
    record = {
        "status": "completed",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "problem": result.problem,
        "provider": result.provider,
        "model": result.model,
        "steps": result.steps,
        "raw_response": result.raw_response,
        "generation_metadata": result.generation_metadata,
        "error_node_id": result.analysis.error_node_id,
        "error_type": result.analysis.error_type,
        "suggested_repair": result.analysis.suggested_repair,
        "correct_answer": result.analysis.correct_answer,
        "affected_node_ids": result.analysis.affected_node_ids,
        "repair_decision": {
            **asdict(result.decision),
            "action": result.decision.action.value,
        },
        "local_repair": {
            "attempted": result.repair.attempted,
            "success": result.repair.success,
            "repaired_steps": result.repair.repaired_steps,
            "replaced_node_id": result.repair.replaced_node_id,
            "replacement": result.repair.replacement,
            "removed_node_ids": result.repair.removed_node_ids,
        },
        "model_repair": {
            "attempted": result.model_repair.attempted,
            "accepted": result.model_repair.accepted,
            "repaired_steps": result.model_repair.repaired_steps,
            "attempts": [asdict(item) for item in result.model_repair.attempts],
        },
    }
    if labels:
        record["labels"] = labels
    append_jsonl_record(path, record)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--provider", choices=["mock", "ollama"], default="mock")
    parser.add_argument("--model", default="")
    parser.add_argument("--problem", default="2(x + 3) = 14")
    parser.add_argument("--save-trace", type=Path)
    parser.add_argument("--model-repair-attempts", type=int, default=1)
    parser.add_argument(
        "--prompt-profile",
        choices=["default", "qwen2_math_json"],
        default="default",
    )
    args = parser.parse_args()

    if args.provider == "ollama":
        if not args.model:
            parser.error("--model is required when using --provider ollama.")
        model_client: MathModel = OllamaMathModel(
            args.model, prompt_profile=args.prompt_profile
        )
        model_name = args.model
    else:
        model_client = MockMathModel()
        model_name = "deliberate-error-mock"

    try:
        result = run_pipeline(
            args.problem,
            model_client,
            args.provider,
            model_name,
            model_repair_attempts=args.model_repair_attempts,
        )
        if args.save_trace:
            save_trace(args.save_trace, result)
    except url_error.URLError as error:
        print(f"MODEL CONNECTION ERROR: {error.reason}")
        print("Make sure Ollama is running and the selected model is installed.")
        return
    except (OSError, ValueError, TypeError, SyntaxError) as error:
        print(f"PIPELINE ERROR: {error}")
        return

    print("=== Model -> MathRepair Pipeline ===")
    print(f"Provider: {result.provider}; model: {result.model}")
    print(f"Problem: {result.problem}\n")
    for index, step in enumerate(result.steps, start=1):
        print(f"Model step {index}: {step}")

    if result.analysis.error_node_id is None:
        print("\nNO ERROR: All model steps are equivalent to the problem.")
    else:
        print(f"\nFirst error node: {result.analysis.error_node_id}")
        print(f"Error type: {result.analysis.error_type}")
        print(f"Repair action: {result.decision.action.value}")
        print(f"Suggested repair: {result.analysis.suggested_repair}")
        affected = ", ".join(result.analysis.affected_node_ids) or "none"
        print(f"Affected nodes: {affected}")
        print(f"Automatic repair success: {result.repair.success}")
        for index, step in enumerate(result.repair.repaired_steps, start=1):
            print(f"Repaired step {index}: {step}")
        print(f"Model repair accepted: {result.model_repair.accepted}")
        for attempt in result.model_repair.attempts:
            status = "ACCEPTED" if attempt.accepted else "REJECTED"
            print(f"Model repair attempt {attempt.attempt_index}: {status}")
            if attempt.rejection_reason:
                print(f"  Reason: {attempt.rejection_reason}")
    print(f"Correct answer: {result.analysis.correct_answer}")
    if args.save_trace:
        print(f"Trace saved: {args.save_trace}")


if __name__ == "__main__":
    main()
