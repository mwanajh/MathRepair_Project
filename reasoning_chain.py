"""Verify a sequence of dependent mathematical reasoning steps."""

from dataclasses import dataclass
from tokenize import TokenError

from mathrepair_demo import ReasoningNode, parse_equation
from reasoning_graph import analyze_graph
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
    verification_mode: str = "symbolic"


def analyze_text_chain(original_text: str, steps: list[str]) -> ChainAnalysis:
    """Build a graph for open-ended benchmark traces without fake verification."""
    nodes = [
        ReasoningNode(
            "n1",
            original_text,
            [],
            subgoal="Represent the benchmark problem",
            model_reasoning=original_text,
            verification_result=None,
            final_status="unverified",
        )
    ]
    for index, step in enumerate(steps, start=2):
        nodes.append(
            ReasoningNode(
                f"n{index}",
                step,
                [f"n{index - 1}"],
                subgoal=f"Advance the solution from n{index - 1}",
                model_reasoning=step,
                verification_result=None,
                final_status="unverified",
            )
        )
    return ChainAnalysis(
        nodes=nodes,
        error_node_id=None,
        error_type="",
        suggested_repair="",
        correct_answer="",
        affected_node_ids=[],
        verification_mode="text_unverified",
    )


def analyze_chain(original_text: str, steps: list[str]) -> ChainAnalysis:
    """Analyze a linear model trace using the canonical reasoning graph."""
    try:
        parse_equation(original_text)
    except (ValueError, TypeError, SyntaxError, TokenError):
        return analyze_text_chain(original_text, steps)

    nodes = [ReasoningNode("n1", original_text, [])]
    for index, step in enumerate(steps, start=2):
        nodes.append(ReasoningNode(f"n{index}", step, [f"n{index - 1}"]))

    graph_analysis = analyze_graph(original_text, nodes)

    return ChainAnalysis(
        nodes=graph_analysis.ordered_nodes,
        error_node_id=graph_analysis.error_node_id,
        error_type=graph_analysis.error_type,
        suggested_repair=graph_analysis.suggested_repair,
        correct_answer=graph_analysis.correct_answer,
        affected_node_ids=graph_analysis.affected_node_ids,
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
