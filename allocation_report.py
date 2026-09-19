"""Write a research-friendly adaptive compute allocation report."""

import argparse
import json
from pathlib import Path

from compute_allocator import allocate_compute
from reasoning_graph import analyze_graph, load_graph


DEFAULT_GRAPH = Path(__file__).with_name("reasoning_graph_example.json")


def build_report(graph_path: Path, budget: int) -> dict[str, object]:
    problem, nodes = load_graph(graph_path)
    analysis = analyze_graph(problem, nodes)
    plans = allocate_compute(
        analysis.ordered_nodes,
        analysis.error_node_id,
        analysis.affected_node_ids,
        budget,
    )
    return {
        "graph": str(graph_path),
        "problem": problem,
        "budget": budget,
        "error_node": analysis.error_node_id,
        "error_type": analysis.error_type,
        "affected_nodes": analysis.affected_node_ids,
        "plans": [
            {
                "node_id": plan.node_id,
                "uncertainty": plan.uncertainty,
                "importance": plan.importance,
                "propagation_risk": plan.propagation_risk,
                "priority": plan.priority,
                "allocated_calls": plan.allocated_calls,
            }
            for plan in plans
        ],
    }


def render_markdown(report: dict[str, object]) -> str:
    lines = [
        "# Adaptive Compute Allocation Report",
        "",
        f"Problem: `{report['problem']}`",
        f"Budget: `{report['budget']}` extra calls",
        f"Error node: `{report['error_node']}` ({report['error_type'] or 'none'})",
        f"Affected nodes: `{', '.join(report['affected_nodes']) or 'none'}`",
        "",
        "| Node | Uncertainty | Importance | Propagation risk | Priority | Allocated calls |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for plan in report["plans"]:
        lines.append(
            f"| {plan['node_id']} | {plan['uncertainty']:.3f} | "
            f"{plan['importance']:.3f} | {plan['propagation_risk']:.3f} | "
            f"{plan['priority']:.3f} | {plan['allocated_calls']} |"
        )
    lines.extend(
        [
            "",
            "Interpretation: extra calls concentrate on the error node and its "
            "affected descendants; unaffected branches receive zero calls.",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--graph", type=Path, default=DEFAULT_GRAPH)
    parser.add_argument("--budget", type=int, default=10)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--markdown", type=Path)
    args = parser.parse_args()
    report = build_report(args.graph, args.budget)
    output = args.output or args.graph.with_name("allocation_report.json")
    markdown = args.markdown or args.graph.with_name("allocation_report.md")
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    markdown.write_text(render_markdown(report), encoding="utf-8")
    print(f"JSON: {output}")
    print(f"Markdown: {markdown}")


if __name__ == "__main__":
    main()
