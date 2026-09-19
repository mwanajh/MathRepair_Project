"""Heuristic node-level test-time compute allocation."""

from dataclasses import dataclass
import math

from mathrepair_demo import ReasoningNode


@dataclass(frozen=True)
class NodeComputePlan:
    """Priority signals and extra model calls assigned to one node."""

    node_id: str
    uncertainty: float
    importance: float
    propagation_risk: float
    priority: float
    allocated_calls: int


def descendant_counts(nodes: list[ReasoningNode]) -> dict[str, int]:
    """Count direct and indirect descendants for every node."""
    children: dict[str, list[str]] = {node.node_id: [] for node in nodes}
    for node in nodes:
        for parent in node.depends_on:
            if parent in children:
                children[parent].append(node.node_id)

    counts: dict[str, int] = {}
    for node in nodes:
        seen: set[str] = set()
        frontier = list(children[node.node_id])
        while frontier:
            child = frontier.pop(0)
            if child in seen:
                continue
            seen.add(child)
            frontier.extend(children[child])
        counts[node.node_id] = len(seen)
    return counts


def allocate_compute(
    nodes: list[ReasoningNode],
    error_node_id: str | None,
    affected_node_ids: list[str],
    budget: int,
) -> list[NodeComputePlan]:
    """Allocate a fixed number of extra calls using U * I * R priority."""
    if budget < 0:
        raise ValueError("Compute budget cannot be negative.")

    counts = descendant_counts(nodes)
    largest_structure = max((count + 1 for count in counts.values()), default=1)
    affected = set(affected_node_ids)
    signals: list[tuple[ReasoningNode, float, float, float, float]] = []

    for node in nodes:
        importance = (counts[node.node_id] + 1) / largest_structure
        if node.node_id == error_node_id:
            uncertainty = 0.95
            propagation_risk = 1.0
        elif node.node_id in affected:
            uncertainty = 0.70
            propagation_risk = 0.75
        else:
            uncertainty = 0.10
            propagation_risk = 0.0
        priority = uncertainty * importance * propagation_risk
        signals.append(
            (node, uncertainty, importance, propagation_risk, priority)
        )

    total_priority = sum(item[4] for item in signals)
    allocations = [0] * len(signals)
    if budget and total_priority:
        exact_allocations = [budget * item[4] / total_priority for item in signals]
        allocations = [math.floor(value) for value in exact_allocations]
        remaining = budget - sum(allocations)
        ranked_indexes = sorted(
            range(len(signals)),
            key=lambda index: (
                exact_allocations[index] - allocations[index],
                signals[index][4],
            ),
            reverse=True,
        )
        for index in ranked_indexes[:remaining]:
            allocations[index] += 1

    return [
        NodeComputePlan(
            node_id=item[0].node_id,
            uncertainty=item[1],
            importance=item[2],
            propagation_risk=item[3],
            priority=item[4],
            allocated_calls=allocations[index],
        )
        for index, item in enumerate(signals)
    ]
