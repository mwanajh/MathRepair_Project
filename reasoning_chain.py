"""Verify a sequence of dependent mathematical reasoning steps."""

from dataclasses import dataclass

from mathrepair_demo import ReasoningNode, verify_reasoning_step
from repair_policy import make_repair_decision


@dataclass
class ChainAnalysis:
    """The result of checking a reasoning chain."""

    nodes: list[ReasoningNode]
    error_node_id: str | None
    error_type: str
    suggested_repair: str
    correct_answer: str
    affected_node_ids: list[str]


def analyze_chain(original_text: str, steps: list[str]) -> ChainAnalysis:
    """Find the first invalid step and its affected downstream nodes."""
    nodes = [ReasoningNode("n1", original_text, [])]
    for index, step in enumerate(steps, start=2):
        nodes.append(ReasoningNode(f"n{index}", step, [f"n{index - 1}"]))

    correct_answer = ""
    for step_index, node in enumerate(nodes[1:], start=1):
        ok, error_type, repair, answer = verify_reasoning_step(
            original_text, node.text
        )
        correct_answer = answer
        if not ok:
            node.error_type = error_type
            downstream = [item.node_id for item in nodes[step_index + 1 :]]
            return ChainAnalysis(
                nodes=nodes,
                error_node_id=node.node_id,
                error_type=error_type,
                suggested_repair=repair,
                correct_answer=answer,
                affected_node_ids=downstream,
            )

    return ChainAnalysis(
        nodes=nodes,
        error_node_id=None,
        error_type="",
        suggested_repair="",
        correct_answer=correct_answer,
        affected_node_ids=[],
    )


def main() -> None:
    print("=== MathRepair: reasoning-chain verifier ===")
    print("Enter the equation, followed by one reasoning step at a time.")
    print("Press Enter on an empty step when finished.\n")

    original_text = input("Original equation: ").strip()
    steps: list[str] = []
    step_number = 1
    while True:
        step = input(f"Step {step_number}: ").strip()
        if not step:
            break
        steps.append(step)
        step_number += 1

    if not steps:
        print("\nINPUT ERROR: Enter at least one solution step.")
        return

    try:
        analysis = analyze_chain(original_text, steps)
    except (ValueError, TypeError, SyntaxError) as error:
        print(f"\nINPUT ERROR: {error}")
        return

    print("\n--- Reasoning graph ---")
    for node in analysis.nodes:
        dependency = ", ".join(node.depends_on) if node.depends_on else "none"
        marker = "  <-- FIRST ERROR" if node.node_id == analysis.error_node_id else ""
        print(f"[{node.node_id}] depends on {dependency}: {node.text}{marker}")

    if analysis.error_node_id is None:
        print("\nNO ERROR: All steps preserve the original equation's solution.")
        print(f"Correct answer: {analysis.correct_answer}")
        return

    print(f"\nFirst error: {analysis.error_node_id}")
    print(f"Error type: {analysis.error_type}")
    decision = make_repair_decision(
        analysis.error_type, analysis.suggested_repair
    )
    print(f"Repair action: {decision.action.value}")
    print(f"Suggested local repair: {analysis.suggested_repair}")
    if analysis.affected_node_ids:
        affected = ", ".join(analysis.affected_node_ids)
        print(f"Affected nodes: {affected}")
    else:
        print("Affected nodes: none")
    print(f"Correct answer: {analysis.correct_answer}")


if __name__ == "__main__":
    main()
