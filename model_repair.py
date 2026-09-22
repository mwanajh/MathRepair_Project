"""Generate local repair candidates and accept only verified solutions."""

from dataclasses import dataclass
from typing import Protocol

from error_taxonomy import INCOMPLETE_SOLUTION
from mathrepair_demo import parse_equation
from reasoning_chain import ChainAnalysis, analyze_chain


class RepairModel(Protocol):
    """A model capable of regenerating a local reasoning suffix."""

    def repair(
        self,
        problem: str,
        valid_prefix: list[str],
        bad_step: str,
        error_type: str,
        attempt_index: int,
    ) -> list[str]:
        """Return candidate replacement steps without receiving the answer."""


@dataclass
class ModelRepairAttempt:
    """One generated candidate and its verifier result."""

    attempt_index: int
    input_valid_prefix: list[str]
    input_trigger_step: str
    input_error_type: str
    candidate_steps: list[str]
    ignored_repeated_prefix: list[str]
    accepted_steps: list[str]
    discarded_steps: list[str]
    accepted: bool
    rejection_reason: str
    first_error_node: str | None
    error_type: str
    raw_response: str
    generation_metadata: dict[str, int | float | str]


@dataclass
class ModelRepairResult:
    """All local generation attempts and the first accepted repaired chain."""

    attempted: bool
    accepted: bool
    repaired_steps: list[str]
    attempts: list[ModelRepairAttempt]


def has_isolated_answer(problem: str, candidate_steps: list[str]) -> bool:
    """Require the generated suffix to end the work with an isolated variable."""
    problem_equation = parse_equation(problem)
    variables = problem_equation.lhs.free_symbols | problem_equation.rhs.free_symbols
    if len(variables) != 1:
        return False
    variable = next(iter(variables))
    for step in candidate_steps:
        equation = parse_equation(step)
        if equation.lhs == variable or equation.rhs == variable:
            return True
    return False


def trim_repeated_parent(
    problem: str,
    valid_prefix: list[str],
    candidate_steps: list[str],
) -> tuple[list[str], list[str]]:
    """Drop a regenerated full chain through its last repeated parent step."""
    if not valid_prefix:
        return candidate_steps, []
    parent = "".join(valid_prefix[-1].split())
    first_answer_index = len(candidate_steps)
    problem_equation = parse_equation(problem)
    variables = problem_equation.lhs.free_symbols | problem_equation.rhs.free_symbols
    if len(variables) == 1:
        variable = next(iter(variables))
        for index, step in enumerate(candidate_steps):
            equation = parse_equation(step)
            if equation.lhs == variable or equation.rhs == variable:
                first_answer_index = index
                break

    repeated_indexes = [
        index
        for index, step in enumerate(candidate_steps[:first_answer_index])
        if "".join(step.split()) == parent
    ]
    if not repeated_indexes:
        return candidate_steps, []
    cut_index = repeated_indexes[-1] + 1
    return candidate_steps[cut_index:], candidate_steps[:cut_index]


def attempt_model_repair(
    problem: str,
    steps: list[str],
    analysis: ChainAnalysis,
    model: object,
    max_attempts: int,
) -> ModelRepairResult:
    """Ask the model for a local suffix and verify every candidate symbolically."""
    if max_attempts < 0:
        raise ValueError("Model repair attempts cannot be negative.")
    repair_method = getattr(model, "repair", None)
    if (
        analysis.verification_mode != "symbolic"
        or analysis.error_node_id is None
        or max_attempts == 0
        or repair_method is None
    ):
        return ModelRepairResult(False, False, [], [])

    error_step_index = int(analysis.error_node_id[1:]) - 2
    if not 0 <= error_step_index < len(steps):
        raise ValueError("Error node does not match the reasoning steps.")
    active_valid_prefix = list(steps[:error_step_index])
    active_trigger_step = steps[error_step_index]
    active_error_type = analysis.error_type
    attempts: list[ModelRepairAttempt] = []

    for attempt_index in range(1, max_attempts + 1):
        candidate_steps: list[str] = []
        input_valid_prefix = list(active_valid_prefix)
        input_trigger_step = active_trigger_step
        input_error_type = active_error_type
        try:
            candidate_steps = repair_method(
                problem,
                input_valid_prefix,
                input_trigger_step,
                input_error_type,
                attempt_index,
            )
            working_candidate_steps, ignored_repeated_prefix = trim_repeated_parent(
                problem, input_valid_prefix, candidate_steps
            )
            full_repaired_steps = input_valid_prefix + working_candidate_steps
            validation = analyze_chain(problem, full_repaired_steps)
            verified_candidate_steps = list(working_candidate_steps)
            if validation.error_node_id is not None:
                first_bad_index = int(validation.error_node_id[1:]) - 2
                verified_count = max(
                    0, first_bad_index - len(input_valid_prefix)
                )
                verified_candidate_steps = working_candidate_steps[:verified_count]

            repaired_steps = input_valid_prefix + verified_candidate_steps
            verified_validation = analyze_chain(problem, repaired_steps)
            isolated_answer = has_isolated_answer(
                problem, verified_candidate_steps
            )
            accepted = (
                verified_validation.error_node_id is None and isolated_answer
            )
            discarded_steps = working_candidate_steps[
                len(verified_candidate_steps) :
            ]
            if validation.error_node_id is not None and not accepted:
                rejection_reason = (
                    f"Verifier rejected {validation.error_node_id}: "
                    f"{validation.error_type}"
                )
            elif not isolated_answer:
                rejection_reason = "Candidate has no isolated final answer."
            else:
                rejection_reason = ""
            first_error_node = validation.error_node_id
            error_type = validation.error_type
        except Exception as error:
            repaired_steps = []
            ignored_repeated_prefix = []
            verified_candidate_steps = []
            discarded_steps = []
            accepted = False
            rejection_reason = str(error)
            first_error_node = None
            error_type = "generation_error"

        attempt = ModelRepairAttempt(
            attempt_index=attempt_index,
            input_valid_prefix=input_valid_prefix,
            input_trigger_step=input_trigger_step,
            input_error_type=input_error_type,
            candidate_steps=candidate_steps,
            ignored_repeated_prefix=ignored_repeated_prefix,
            accepted_steps=verified_candidate_steps,
            discarded_steps=discarded_steps,
            accepted=accepted,
            rejection_reason=rejection_reason,
            first_error_node=first_error_node,
            error_type=error_type,
            raw_response=str(getattr(model, "last_repair_raw_response", "")),
            generation_metadata=dict(
                getattr(model, "last_repair_metadata", {})
            ),
        )
        attempts.append(attempt)
        if accepted:
            return ModelRepairResult(True, True, repaired_steps, attempts)

        if repaired_steps and verified_candidate_steps:
            active_valid_prefix = repaired_steps
            if discarded_steps:
                active_trigger_step = discarded_steps[0]
                active_error_type = error_type or analysis.error_type
            else:
                active_trigger_step = repaired_steps[-1]
                active_error_type = INCOMPLETE_SOLUTION

    return ModelRepairResult(True, False, [], attempts)
