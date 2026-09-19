import unittest

from graph_web_server import analyze_payload


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


if __name__ == "__main__":
    unittest.main()
