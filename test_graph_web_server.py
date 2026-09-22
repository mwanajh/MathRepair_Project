import unittest

from graph_web_server import analyze_payload, generate_reasoning_steps


class GraphWebServerTests(unittest.TestCase):
    def test_analyzes_submitted_trace_and_returns_graph_statuses(self):
        result = analyze_payload(
            {
                "problem": "2(x + 3) = 14",
                "steps": ["2x + 3 = 14", "2x = 11", "x = 5.5"],
            }
        )

        self.assertEqual(result["error_node_id"], "n1")
        self.assertEqual(result["repair_action"], "REFORMALIZE")
        self.assertEqual(result["correct_answer"], "x = 4")
        self.assertEqual(
            [node["status"] for node in result["nodes"]],
            ["error", "affected", "affected"],
        )
        self.assertEqual(
            [item["allocated_calls"] for item in result["allocation"]],
            [7, 2, 1],
        )

    def test_rejects_empty_submitted_steps(self):
        with self.assertRaisesRegex(ValueError, "at least one"):
            analyze_payload({"problem": "2x = 8", "steps": []})

    def test_generates_trace_for_expanded_linear_equation(self):
        self.assertEqual(
            generate_reasoning_steps("2(x + 3) = 14"),
            ["2x + 6 = 14", "2x = 8", "x = 4"],
        )

    def test_generates_trace_when_variable_is_on_both_sides(self):
        self.assertEqual(
            generate_reasoning_steps("2x + 3 = x + 7"),
            ["2x + 3 = x + 7", "x = 4"],
        )

    def test_rejects_automatic_trace_without_one_solution(self):
        with self.assertRaisesRegex(ValueError, "one real solution"):
            generate_reasoning_steps("x = x")

    def test_detects_false_arithmetic_problem(self):
        steps = generate_reasoning_steps("7 + 5 = 13")
        result = analyze_payload({"problem": "7 + 5 = 13", "steps": steps})

        self.assertEqual(steps, ["7 + 5 = 13"])
        self.assertEqual(result["error_node_id"], "n1")
        self.assertEqual(result["error_type"], "arithmetic_error")
        self.assertEqual(result["suggested_repair"], "7 + 5 = 12")
        self.assertEqual(result["correct_answer"], "7 + 5 = 12")
        self.assertEqual(result["nodes"][0]["status"], "error")

    def test_accepts_true_arithmetic_problem(self):
        result = analyze_payload(
            {"problem": "7 + 5 = 12", "steps": ["7 + 5 = 12"]}
        )

        self.assertIsNone(result["error_node_id"])
        self.assertEqual(result["nodes"][0]["status"], "clear")


if __name__ == "__main__":
    unittest.main()
