import unittest
from pathlib import Path

from allocation_report import build_report, render_markdown


class AllocationReportTests(unittest.TestCase):
    def test_reports_exact_budget_and_unaffected_branch(self):
        report = build_report(Path("reasoning_graph_example.json"), budget=10)
        self.assertEqual(
            sum(plan["allocated_calls"] for plan in report["plans"]), 10
        )
        plans = {plan["node_id"]: plan for plan in report["plans"]}
        self.assertEqual(plans["n4"]["allocated_calls"], 0)
        self.assertIn("Adaptive Compute Allocation Report", render_markdown(report))


if __name__ == "__main__":
    unittest.main()
