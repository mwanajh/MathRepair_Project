"""Serve the MathRepair graph demo and analyze user-entered traces."""

import argparse
import json
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from compute_allocator import allocate_compute
from mathrepair_demo import ReasoningNode
from repair_policy import make_repair_decision
from reasoning_graph import analyze_graph


PROJECT_DIR = Path(__file__).resolve().parent


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

    analysis = analyze_graph(problem.strip(), nodes)
    decision = make_repair_decision(
        analysis.error_type, analysis.suggested_repair
    )
    plans = allocate_compute(
        analysis.ordered_nodes,
        analysis.error_node_id,
        analysis.affected_node_ids,
        10,
    )
    affected = set(analysis.affected_node_ids)
    output_nodes = []
    for node in analysis.ordered_nodes:
        if node.node_id == analysis.error_node_id:
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
        "error_node_id": analysis.error_node_id,
        "error_type": analysis.error_type,
        "suggested_repair": analysis.suggested_repair,
        "repair_action": decision.action.value,
        "repair_reason": decision.reason,
        "correct_answer": analysis.correct_answer,
        "affected_node_ids": analysis.affected_node_ids,
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
        if self.path != "/api/analyze":
            self.send_error(404, "Unknown endpoint")
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
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
