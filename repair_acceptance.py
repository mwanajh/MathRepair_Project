"""Decide whether a generated repair may replace the original trace.

The gate compares the two traces with the symbolic checker. It accepts a
replacement only when the repaired trace is fully verified and the original
trace is not. It never receives the benchmark reference answer.
"""

from dataclasses import dataclass
from tokenize import TokenError

from reasoning_chain import analyze_chain


@dataclass(frozen=True)
class RepairAcceptance:
    """The comparison of an original trace and one generated replacement."""

    accepted: bool
    reason: str
    original_verification_mode: str
    repaired_verification_mode: str


def _inspect(problem: str, steps: list[str]) -> tuple[str, bool]:
    """Return the verification mode and whether every step is symbolically valid."""
    if not steps:
        return "empty", False
    try:
        analysis = analyze_chain(problem, steps)
    except (ValueError, TypeError, SyntaxError, ArithmeticError, TokenError):
        return "unreadable", False
    if analysis.verification_mode != "symbolic":
        return analysis.verification_mode, False
    return "symbolic", analysis.error_node_id is None


def compare_repair_states(
    problem: str,
    original_steps: list[str],
    repaired_steps: list[str],
) -> RepairAcceptance:
    """Reject a replacement that is not symbolically more reliable than the original."""
    original_mode, original_verified = _inspect(problem, original_steps)
    repaired_mode, repaired_verified = _inspect(problem, repaired_steps)
    if repaired_mode != "symbolic" or original_mode != "symbolic":
        return RepairAcceptance(
            False,
            "The two states are not both symbolically comparable, so the repair is not more reliable.",
            original_mode,
            repaired_mode,
        )
    if not repaired_verified:
        return RepairAcceptance(
            False,
            "The repaired trace still has a symbolic error.",
            original_mode,
            repaired_mode,
        )
    if original_verified:
        return RepairAcceptance(
            False,
            "The original trace is already symbolically verified.",
            original_mode,
            repaired_mode,
        )
    return RepairAcceptance(
        True,
        "The repaired trace is symbolically verified and the original trace is not.",
        original_mode,
        repaired_mode,
    )
