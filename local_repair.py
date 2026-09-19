"""Apply and verify a targeted repair to a linear reasoning chain."""

from dataclasses import dataclass

from reasoning_chain import ChainAnalysis, analyze_chain


@dataclass
class LocalRepairResult:
    """The repaired suffix and the result of verifying it again."""

    attempted: bool
    success: bool
    repaired_steps: list[str]
    replaced_node_id: str | None
    replacement: str
    removed_node_ids: list[str]
    validation: ChainAnalysis


def apply_local_repair(
    problem: str,
    steps: list[str],
    analysis: ChainAnalysis | None = None,
) -> LocalRepairResult:
    """Replace the first bad node and discard only its affected suffix."""
    initial_analysis = analysis or analyze_chain(problem, steps)
    if initial_analysis.error_node_id is None:
        return LocalRepairResult(
            attempted=False,
            success=True,
            repaired_steps=list(steps),
            replaced_node_id=None,
            replacement="",
            removed_node_ids=[],
            validation=initial_analysis,
        )

    error_step_index = int(initial_analysis.error_node_id[1:]) - 2
    if not 0 <= error_step_index < len(steps):
        raise ValueError("Error node does not match the reasoning steps.")

    repaired_steps = list(steps[:error_step_index])
    replacement = initial_analysis.suggested_repair.strip()
    if replacement:
        repaired_steps.append(replacement)

    correct_answer = initial_analysis.correct_answer.strip()
    if (
        correct_answer.count("=") == 1
        and (not repaired_steps or repaired_steps[-1] != correct_answer)
    ):
        repaired_steps.append(correct_answer)

    validation = analyze_chain(problem, repaired_steps)
    return LocalRepairResult(
        attempted=True,
        success=validation.error_node_id is None,
        repaired_steps=repaired_steps,
        replaced_node_id=initial_analysis.error_node_id,
        replacement=replacement,
        removed_node_ids=list(initial_analysis.affected_node_ids),
        validation=validation,
    )
