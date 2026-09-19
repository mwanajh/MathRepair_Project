"""Verify a branching mathematical reasoning graph loaded from JSON."""

from dataclasses import dataclass
import json
from pathlib import Path
import sys

from compute_allocator import allocate_compute
from mathrepair_demo import ReasoningNode, verify_reasoning_step
from repair_policy import make_repair_decision


DEFAULT_GRAPH_FILE = Path(__file__).with_name("reasoning_graph_example.json")
DEFAULT_COMPUTE_BUDGET = 10


@dataclass
class GraphAnalysis:
    """The first error and its structural impact in a reasoning graph."""

    ordered_nodes: list[ReasoningNode]
    error_node_id: str | None
    error_type: str
    suggested_repair: str
    correct_answer: str
    affected_node_ids: list[str]


def topological_order(nodes: list[ReasoningNode]) -> list[ReasoningNode]:
    """Validate dependencies and order parents before their children."""
    node_by_id: dict[str, ReasoningNode] = {}
    for node in nodes:
        if node.node_id == "problem":
            raise ValueError("'problem' is reserved; use a different node ID.")
        if node.node_id in node_by_id:
            raise ValueError(f"Duplicate node ID: {node.node_id}")
        node_by_id[node.node_id] = node

    for node in nodes:
        for dependency in node.depends_on:
            if dependency != "problem" and dependency not in node_by_id:
                raise ValueError(
                    f"Node {node.node_id} depends on a missing node: {dependency}"
                )

    ordered: list[ReasoningNode] = []
    completed = {"problem"}
    remaining = list(nodes)
    while remaining:
        ready = [
            node
            for node in remaining
            if all(dependency in completed for dependency in node.depends_on)
        ]
        if not ready:
            raise ValueError("Graph contains a cycle; dependencies cannot be resolved.")
        for node in ready:
            ordered.append(node)
            completed.add(node.node_id)
            remaining.remove(node)

    return ordered


def find_descendants(nodes: list[ReasoningNode], node_id: str) -> list[str]:
    """Return every node that directly or indirectly depends on node_id."""
    descendants: list[str] = []
    frontier = [node_id]
    while frontier:
        parent = frontier.pop(0)
        for node in nodes:
            if parent in node.depends_on and node.node_id not in descendants:
                descendants.append(node.node_id)
                frontier.append(node.node_id)
    return descendants


def analyze_graph(problem: str, nodes: list[ReasoningNode]) -> GraphAnalysis:
    """Locate the first erroneous node and trace only its descendants."""
    ordered = topological_order(nodes)
    correct_answer = ""

    for node in ordered:
        ok, error_type, repair, answer = verify_reasoning_step(
            problem, node.text
        )
        correct_answer = answer
        if not ok:
            node.error_type = error_type
            affected = find_descendants(ordered, node.node_id)
            return GraphAnalysis(
                ordered_nodes=ordered,
                error_node_id=node.node_id,
                error_type=error_type,
                suggested_repair=repair,
                correct_answer=answer,
                affected_node_ids=affected,
            )

    return GraphAnalysis(
        ordered_nodes=ordered,
        error_node_id=None,
        error_type="",
        suggested_repair="",
        correct_answer=correct_answer,
        affected_node_ids=[],
    )


def load_graph(path: Path) -> tuple[str, list[ReasoningNode]]:
    """Load the problem and nodes from a JSON file."""
    with path.open(encoding="utf-8") as file:
        data = json.load(file)

    if not isinstance(data.get("problem"), str) or not data["problem"].strip():
        raise ValueError("JSON must contain a non-empty 'problem' equation.")
    if not isinstance(data.get("nodes"), list) or not data["nodes"]:
        raise ValueError("JSON must contain a non-empty 'nodes' list.")

    nodes: list[ReasoningNode] = []
    for item in data["nodes"]:
        if not isinstance(item, dict):
            raise ValueError("Each node must be a JSON object.")
        try:
            node_id = item["id"]
            text = item["text"]
            depends_on = item["depends_on"]
        except KeyError as error:
            raise ValueError(f"Node is missing field: {error.args[0]}") from error
        if not isinstance(node_id, str) or not isinstance(text, str):
            raise ValueError("'id' and 'text' must be strings.")
        if not isinstance(depends_on, list) or not all(
            isinstance(value, str) for value in depends_on
        ):
            raise ValueError("'depends_on' must be a list of node IDs.")
        nodes.append(ReasoningNode(node_id, text, depends_on))

    return data["problem"], nodes


def main() -> None:
    graph_file = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_GRAPH_FILE
    print("=== MathRepair: branching reasoning graph ===")
    print(f"Graph file: {graph_file}\n")

    try:
        problem, nodes = load_graph(graph_file)
        analysis = analyze_graph(problem, nodes)
    except (OSError, json.JSONDecodeError, ValueError, TypeError, SyntaxError) as error:
        print(f"GRAPH ERROR: {error}")
        return

    affected = set(analysis.affected_node_ids)
    print(f"[problem] {problem}")
    for node in analysis.ordered_nodes:
        dependencies = ", ".join(node.depends_on) or "none"
        if node.node_id == analysis.error_node_id:
            status = "ERROR"
        elif node.node_id in affected:
            status = "AFFECTED"
        else:
            status = "UNAFFECTED"
        print(
            f"[{node.node_id}] depends on {dependencies}: "
            f"{node.text}  [{status}]"
        )

    if analysis.error_node_id is None:
        print("\nNO ERROR: The entire graph is valid.")
    else:
        print(f"\nFirst error: {analysis.error_node_id}")
        print(f"Error type: {analysis.error_type}")
        decision = make_repair_decision(
            analysis.error_type, analysis.suggested_repair
        )
        print(f"Repair action: {decision.action.value}")
        print(f"Reason: {decision.reason}")
        print(f"Suggested local repair: {analysis.suggested_repair}")
        affected_text = ", ".join(analysis.affected_node_ids) or "none"
        print(f"Affected descendants: {affected_text}")
        print(f"Correct answer: {analysis.correct_answer}")

    plans = allocate_compute(
        analysis.ordered_nodes,
        analysis.error_node_id,
        analysis.affected_node_ids,
        DEFAULT_COMPUTE_BUDGET,
    )
    print(f"\n--- Adaptive compute plan (budget={DEFAULT_COMPUTE_BUDGET}) ---")
    for plan in plans:
        print(
            f"[{plan.node_id}] priority={plan.priority:.3f}, "
            f"extra calls={plan.allocated_calls}"
        )


if __name__ == "__main__":
    main()
