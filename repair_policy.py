"""Rule-based repair policy for the first MathRepair baseline."""

from dataclasses import dataclass
from enum import Enum

from error_taxonomy import get_error_spec


class RepairAction(str, Enum):
    """Repair operations currently supported by the prototype."""

    CONTINUE = "CONTINUE"
    TOOL_EXECUTE = "TOOL_EXECUTE"
    BACKTRACK = "BACKTRACK"
    REFORMALIZE = "REFORMALIZE"
    LOCAL_RESAMPLE = "LOCAL_RESAMPLE"
    REPLAN = "REPLAN"


@dataclass(frozen=True)
class RepairDecision:
    """An action selected from a diagnosed error type."""

    action: RepairAction
    reason: str
    replacement: str


def choose_repair_action(error_type: str) -> RepairAction:
    """Map an error diagnosis to a targeted repair operation."""
    if not error_type:
        return RepairAction.CONTINUE
    spec = get_error_spec(error_type)
    if spec is None:
        return RepairAction.LOCAL_RESAMPLE
    return RepairAction(spec.recommended_actions[0])


def make_repair_decision(error_type: str, replacement: str) -> RepairDecision:
    """Build a human-readable repair decision."""
    action = choose_repair_action(error_type)
    reasons = {
        RepairAction.CONTINUE: "The step is correct; continue reasoning.",
        RepairAction.TOOL_EXECUTE: "Recompute using the symbolic calculator.",
        RepairAction.BACKTRACK: "Return to the parent node and check the operation sign.",
        RepairAction.REFORMALIZE: "Expand or simplify the equation symbolically.",
        RepairAction.LOCAL_RESAMPLE: "Regenerate only this node.",
        RepairAction.REPLAN: "Reconstruct the missing assumptions or reasoning plan.",
    }
    return RepairDecision(action, reasons[action], replacement)
