"""Serve the MathRepair graph demo and analyze user-entered traces."""

import argparse
import json
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

import sympy as sp

from compute_allocator import allocate_compute
from mathrepair_demo import (
    ReasoningNode,
    equation_variables,
    format_expression,
    normalize_solution_set,
    parse_equation,
)
from repair_policy import make_repair_decision
from reasoning_graph import analyze_graph


PROJECT_DIR = Path(__file__).resolve().parent


def _format_equation(left: sp.Expr, right: sp.Expr) -> str:
    return f"{format_expression(left)} = {format_expression(right)}"


def generate_reasoning_steps(problem: str) -> list[str]:
    """Generate a short, valid trace for a one-variable equation."""
    if not isinstance(problem, str) or not problem.strip():
        raise ValueError("Problem equation is required.")

    equation = parse_equation(problem.strip())
    variables = equation_variables(equation)
    if not variables:
        return [problem.strip()]
    if len(variables) != 1:
        raise ValueError("Automatic trace generation requires exactly one variable.")

    variable = next(iter(variables))
    solutions = normalize_solution_set(
        sp.solveset(equation, variable, domain=sp.S.Reals)
    )
    if not isinstance(solutions, sp.FiniteSet) or len(solutions) != 1:
        raise ValueError("Automatic trace generation requires one real solution.")

    solution = next(iter(solutions))
    expanded_left = sp.expand(equation.lhs)
    expanded_right = sp.expand(equation.rhs)
    expanded_step = _format_equation(expanded_left, expanded_right)
    steps: list[str] = [expanded_step]

    try:
        polynomial = sp.Poly(sp.expand(equation.lhs - equation.rhs), variable)
    except sp.PolynomialError:
        polynomial = None

    if polynomial is not None and polynomial.degree() == 1:
        coefficient = sp.simplify(polynomial.coeff_monomial(variable))
        constant = sp.simplify(polynomial.coeff_monomial(1))
        isolated_term = _format_equation(coefficient * variable, -constant)
        if isolated_term not in steps:
            steps.append(isolated_term)

    answer_step = _format_equation(variable, solution)
    if answer_step not in steps:
        steps.append(answer_step)
    return steps


def analyze_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Build a linear dependency graph from submitted steps and verify it."""
    problem = payload.get("problem")
    raw_steps = payload.get("steps")
    if not isinstance(problem, str) or not problem.strip():
        raise ValueError("Problem equation is required.")
    if not isinstance(raw_steps, list):
        raise ValueError("Steps must be a list of equation strings.")
    steps = [str(step).strip() for step in raw_steps if str(step).strip()]
    if not steps:
        raise ValueError("Enter at least one reasoning step.")

    nodes: list[ReasoningNode] = []
    previous = "problem"
    for index, step in enumerate(steps, start=1):
        node_id = f"n{index}"
        nodes.append(ReasoningNode(node_id, step, [previous]))
        previous = node_id

    problem_text = problem.strip()
    problem_equation = parse_equation(problem_text)
    if equation_variables(problem_equation):
        analysis = analyze_graph(problem_text, nodes)
        error_node_id = analysis.error_node_id
        error_type = analysis.error_type
        suggested_repair = analysis.suggested_repair
        correct_answer = analysis.correct_answer
        affected_node_ids = analysis.affected_node_ids
        ordered_nodes = analysis.ordered_nodes
    else:
        is_correct = sp.simplify(
            problem_equation.lhs - problem_equation.rhs
        ) == 0
        left_text = problem_text.split("=", maxsplit=1)[0].strip()
        evaluated_left = format_expression(sp.simplify(problem_equation.lhs))
        corrected_equation = f"{left_text} = {evaluated_left}"
        error_node_id = None if is_correct else nodes[0].node_id
        error_type = "" if is_correct else "arithmetic_error"
        suggested_repair = "" if is_correct else corrected_equation
        correct_answer = corrected_equation
        affected_node_ids = (
            [] if is_correct else [node.node_id for node in nodes[1:]]
        )
        ordered_nodes = nodes

    decision = make_repair_decision(
        error_type, suggested_repair
    )
    plans = allocate_compute(
        ordered_nodes,
        error_node_id,
        affected_node_ids,
        10,
    )
    affected = set(affected_node_ids)
    output_nodes = []
    for node in ordered_nodes:
        if node.node_id == error_node_id:
            status = "error"
        elif node.node_id in affected:
            status = "affected"
        else:
            status = "clear"
        output_nodes.append(
            {
                "id": node.node_id,
                "text": node.text,
                "depends_on": node.depends_on,
                "status": status,
            }
        )
    return {
        "problem": problem.strip(),
        "nodes": output_nodes,
        "error_node_id": error_node_id,
        "error_type": error_type,
        "suggested_repair": suggested_repair,
        "repair_action": decision.action.value,
        "repair_reason": decision.reason,
        "correct_answer": correct_answer,
        "affected_node_ids": affected_node_ids,
        "allocation": [
            {
                "node_id": plan.node_id,
                "priority": plan.priority,
                "allocated_calls": plan.allocated_calls,
            }
            for plan in plans
        ],
    }


class DemoHandler(SimpleHTTPRequestHandler):
    """Serve static demo assets and a small JSON analysis endpoint."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, directory=str(PROJECT_DIR), **kwargs)

    def do_POST(self) -> None:  # noqa: N802 - required by BaseHTTPRequestHandler
        if self.path not in {"/api/analyze", "/api/generate-trace"}:
            self.send_error(404, "Unknown endpoint")
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
            if self.path == "/api/generate-trace":
                problem = payload.get("problem")
                result = {
                    "problem": problem.strip() if isinstance(problem, str) else "",
                    "steps": generate_reasoning_steps(problem),
                }
            else:
                result = analyze_payload(payload)
            self._send_json(200, result)
        except (
            ValueError,
            TypeError,
            json.JSONDecodeError,
            SyntaxError,
            IndexError,
        ) as error:
            self._send_json(400, {"error": str(error)})

    def _send_json(self, status: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def end_headers(self) -> None:
        # The demo is edited during a defense/demo session; never keep an old
        # HTML, CSS, or JavaScript bundle after the server has been restarted.
        self.send_header("Cache-Control", "no-store, max-age=0")
        super().end_headers()

    def do_GET(self) -> None:  # noqa: N802 - required by BaseHTTPRequestHandler
        if self.path == "/api/health":
            self._send_json(200, {"status": "ok"})
            return
        super().do_GET()

    def log_message(self, format: str, *args: object) -> None:
        return


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    server = ThreadingHTTPServer((args.host, args.port), DemoHandler)
    print(f"MathRepair Graph Lab: http://{args.host}:{args.port}/graph_demo.html")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
