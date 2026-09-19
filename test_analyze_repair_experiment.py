import unittest

from analyze_repair_experiment import build_experiment_summary, render_markdown


class RepairExperimentAnalysisTests(unittest.TestCase):
    def test_builds_strategy_and_efficiency_metrics(self):
        report = {
            "model": "test-model",
            "problem_count": 2,
            "samples_per_problem": 1,
            "temperature": 0.0,
            "base_seed": 1,
            "total_eval_tokens": 100,
            "model_repair_eval_tokens": 20,
            "results": [
                {
                    "status": "completed",
                    "problem": "2x = 8",
                    "category": "linear",
                    "expected_answer": "x = 4",
                    "answer_correct": True,
                    "model_trace_valid": True,
                    "auto_repair_success": True,
                    "repaired_steps": ["x = 4"],
                    "model_repair_attempted": False,
                    "model_repair_accepted": False,
                    "model_repair_attempt_count": 0,
                    "model_repaired_steps": [],
                    "error_type": "",
                },
                {
                    "status": "completed",
                    "problem": "3x = 9",
                    "category": "linear",
                    "expected_answer": "x = 3",
                    "answer_correct": False,
                    "model_trace_valid": False,
                    "auto_repair_success": True,
                    "repaired_steps": ["x = 3"],
                    "model_repair_attempted": True,
                    "model_repair_accepted": True,
                    "model_repair_attempt_count": 1,
                    "model_repaired_steps": ["x = 3"],
                    "error_type": "arithmetic_error",
                },
            ],
        }

        summary = build_experiment_summary(report)

        baseline, symbolic, model = summary["strategies"]
        self.assertEqual(baseline["answer_accuracy"], 0.5)
        self.assertEqual(symbolic["answer_accuracy"], 1.0)
        self.assertEqual(model["answer_accuracy"], 1.0)
        self.assertEqual(model["trace_valid_rate"], 1.0)
        self.assertEqual(model["model_calls"], 3)
        self.assertEqual(model["inference_tokens"], 120)
        self.assertEqual(
            summary["repair_metrics"]["wrong_answer_recovery_rate"], 1.0
        )
        self.assertEqual(
            summary["efficiency_metrics"]["repair_token_overhead_rate"], 0.2
        )

    def test_renders_thesis_ready_markdown(self):
        report = {
            "model": "test-model",
            "problem_count": 1,
            "samples_per_problem": 1,
            "total_eval_tokens": 10,
            "model_repair_eval_tokens": 0,
            "results": [
                {
                    "status": "completed",
                    "problem": "x = 1",
                    "category": "linear",
                    "expected_answer": "x = 1",
                    "answer_correct": True,
                    "model_trace_valid": True,
                    "auto_repair_success": True,
                    "repaired_steps": ["x = 1"],
                    "model_repair_attempted": False,
                    "model_repair_accepted": False,
                    "model_repair_attempt_count": 0,
                    "model_repaired_steps": [],
                    "error_type": "",
                }
            ],
        }

        markdown = render_markdown(build_experiment_summary(report))

        self.assertIn("## Strategy Comparison", markdown)
        self.assertIn("| no_repair | 100.0%", markdown)
        self.assertIn("## Results By Category", markdown)
        self.assertIn("| linear | 1 | 1/1 | 1/1", markdown)
        self.assertIn("matched token budgets", markdown)

    def test_includes_a_valid_matched_budget_comparison(self):
        report = {
            "model": "test-model",
            "problem_count": 1,
            "samples_per_problem": 1,
            "total_eval_tokens": 10,
            "model_repair_eval_tokens": 0,
            "results": [
                {
                    "status": "completed",
                    "problem": "x = 1",
                    "category": "linear",
                    "expected_answer": "x = 1",
                    "answer_correct": True,
                    "model_trace_valid": True,
                    "auto_repair_success": True,
                    "repaired_steps": ["x = 1"],
                    "model_repair_attempted": False,
                    "model_repair_accepted": False,
                    "model_repair_attempt_count": 0,
                    "model_repaired_steps": [],
                    "error_type": "",
                }
            ],
        }
        matched = {
            "matched_budget_comparison_valid": True,
            "budget_definition": "Same per-run token ceiling.",
            "global_budget_utilization_rate": 0.8,
            "budget_violation_count": 0,
            "strategies": [
                {
                    "name": "verified_local_repair",
                    "answer_accuracy": 1.0,
                    "trace_valid_rate": 1.0,
                    "additional_model_calls": 1,
                    "additional_tokens": 10,
                }
            ],
        }

        summary = build_experiment_summary(report, matched)
        markdown = render_markdown(summary)

        self.assertTrue(summary["matched_budget_comparison_available"])
        self.assertIn("## Matched-Budget Comparison", markdown)
        self.assertNotIn("not yet been compared", markdown)


if __name__ == "__main__":
    unittest.main()
