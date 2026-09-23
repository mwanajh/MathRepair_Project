import unittest

from matched_budget_experiment import (
    adaptive_risk_score,
    allocate_integer_budget,
    run_matched_budget,
)


class FakeGlobalModel:
    def __init__(self):
        self.last_metadata = {"prompt_eval_count": 5, "eval_count": 10}

    def solve(self, problem):
        return ["3x = 9", "x = 3"]


class TransientFailureModel:
    def __init__(self):
        self.last_metadata = {}

    def solve(self, problem):
        raise ConnectionError("temporary transport failure")


class FakeLocalModel:
    def __init__(self):
        self.last_repair_metadata = {"prompt_eval_count": 5, "eval_count": 10}

    def repair(self, problem, valid_prefix, bad_step, error_type, attempt_index):
        return ["3x = 9", "x = 3"]


class MatchedBudgetExperimentTests(unittest.TestCase):
    def test_integer_budget_allocation_preserves_total(self):
        allocation = allocate_integer_budget(10, [1.0, 2.0, 3.0])

        self.assertEqual(sum(allocation), 10)
        self.assertGreater(allocation[2], allocation[0])

    def test_adaptive_risk_prioritizes_early_high_impact_error(self):
        early = {
            "step_count": 8,
            "first_error_node": "n2",
            "error_type": "algebraic_transformation_error",
        }
        late = {
            "step_count": 8,
            "first_error_node": "n8",
            "error_type": "arithmetic_error",
        }

        self.assertGreater(adaptive_risk_score(early), adaptive_risk_score(late))

    def test_compares_global_and_local_under_the_same_token_cap(self):
        completion_caps = []

        def factory(record, completion_cap, attempt_index):
            completion_caps.append(completion_cap)
            return FakeGlobalModel()

        report = {
            "model": "test-model",
            "temperature": 0.0,
            "model_repair_accept_count": 1,
            "model_repair_attempt_count": 1,
            "results": [
                {
                    "status": "completed",
                    "seed": 1,
                    "temperature": 0.0,
                    "problem": "2x = 8",
                    "category": "linear",
                    "expected_answer": "x = 4",
                    "answer_correct": True,
                    "model_trace_valid": True,
                    "generation_metadata": {
                        "prompt_eval_count": 5,
                        "eval_count": 5,
                    },
                    "model_repair_attempts": [],
                    "post_model_repair_answer_correct": True,
                    "post_model_repair_trace_valid": True,
                },
                {
                    "status": "completed",
                    "seed": 2,
                    "temperature": 0.0,
                    "problem": "3x = 9",
                    "category": "linear",
                    "expected_answer": "x = 3",
                    "answer_correct": False,
                    "model_trace_valid": False,
                    "generation_metadata": {
                        "prompt_eval_count": 5,
                        "eval_count": 5,
                    },
                    "model_repair_attempts": [
                        {
                            "generation_metadata": {
                                "prompt_eval_count": 5,
                                "eval_count": 10,
                            }
                        }
                    ],
                    "post_model_repair_answer_correct": True,
                    "post_model_repair_trace_valid": True,
                },
            ],
        }

        summary = run_matched_budget(report, model_factory=factory)

        self.assertEqual(completion_caps, [10])
        self.assertTrue(summary["matched_budget_comparison_valid"])
        self.assertEqual(summary["global_regeneration_additional_tokens"], 15)
        global_strategy = summary["strategies"][1]
        self.assertEqual(global_strategy["answer_accuracy"], 1.0)
        self.assertEqual(global_strategy["trace_valid_rate"], 1.0)
        self.assertEqual(
            [item["name"] for item in summary["strategies"]],
            [
                "no_repair",
                "verified_global_regeneration",
                "verified_local_repair_uniform",
                "verified_local_repair_adaptive",
            ],
        )
        for strategy in summary["strategies"]:
            self.assertIn("repair_success_rate", strategy)
            self.assertIn("average_model_calls", strategy)
            self.assertIn("average_tokens", strategy)
            self.assertIn("total_compute_cost", strategy)
        self.assertEqual(
            summary["strategies"][3]["allocated_additional_tokens"],
            summary["matched_additional_token_budget"],
        )

    def test_retries_a_zero_token_infrastructure_failure(self):
        calls = 0

        def factory(record, completion_cap, attempt_index):
            nonlocal calls
            calls += 1
            return TransientFailureModel() if calls == 1 else FakeGlobalModel()

        report = {
            "model": "test-model",
            "temperature": 0.0,
            "model_repair_accept_count": 1,
            "model_repair_attempt_count": 1,
            "results": [
                {
                    "status": "completed",
                    "seed": 2,
                    "temperature": 0.0,
                    "problem": "3x = 9",
                    "category": "linear",
                    "expected_answer": "x = 3",
                    "answer_correct": False,
                    "model_trace_valid": False,
                    "generation_metadata": {"prompt_eval_count": 5},
                    "model_repair_attempts": [
                        {
                            "generation_metadata": {
                                "prompt_eval_count": 5,
                                "eval_count": 10,
                            }
                        }
                    ],
                    "post_model_repair_answer_correct": True,
                    "model_repair_accepted": True,
                }
            ],
        }

        summary = run_matched_budget(report, model_factory=factory)

        self.assertEqual(calls, 2)
        attempt = summary["global_regeneration_results"][0]["attempts"][0]
        self.assertEqual(attempt["infrastructure_retries"], 1)
        self.assertTrue(attempt["accepted"])

    def test_runs_fresh_uniform_and_adaptive_local_arms(self):
        report = {
            "model": "test-model",
            "temperature": 0.0,
            "results": [
                {
                    "status": "completed",
                    "seed": 2,
                    "temperature": 0.0,
                    "problem": "3x = 9",
                    "category": "linear",
                    "expected_answer": "x = 3",
                    "answer_correct": False,
                    "model_trace_valid": False,
                    "first_error_node": "n2",
                    "error_type": "algebraic_transformation_error",
                    "step_count": 2,
                    "generation_metadata": {
                        "prompt_eval_count": 5,
                        "eval_count": 5,
                    },
                    "model_repair_attempts": [
                        {
                            "input_valid_prefix": [],
                            "input_trigger_step": "x = 2",
                            "input_error_type": "algebraic_transformation_error",
                            "generation_metadata": {
                                "prompt_eval_count": 5,
                                "eval_count": 10,
                            },
                        }
                    ],
                }
            ],
        }

        summary = run_matched_budget(
            report,
            model_factory=lambda *args: FakeGlobalModel(),
            live_local=True,
            uniform_local_factory=lambda *args: FakeLocalModel(),
            adaptive_local_factory=lambda *args: FakeLocalModel(),
        )

        self.assertEqual(summary["local_evaluation_mode"], "live")
        for strategy in summary["strategies"][2:]:
            self.assertEqual(strategy["answer_accuracy"], 1.0)
            self.assertEqual(strategy["trace_valid_rate"], 1.0)
            self.assertEqual(strategy["repair_success_rate"], 1.0)
            self.assertTrue(strategy["budget_respected"])

    def test_keeps_failed_generations_in_accuracy_denominator(self):
        report = {
            "model": "test-model",
            "temperature": 0.0,
            "model_repair_accept_count": 0,
            "model_repair_attempt_count": 1,
            "results": [
                {
                    "status": "completed",
                    "seed": 1,
                    "temperature": 0.0,
                    "problem": "3x = 9",
                    "category": "linear",
                    "expected_answer": "x = 3",
                    "answer_correct": False,
                    "model_trace_valid": False,
                    "generation_metadata": {"prompt_eval_count": 5},
                    "model_repair_attempts": [
                        {
                            "generation_metadata": {
                                "prompt_eval_count": 5,
                                "eval_count": 10,
                            }
                        }
                    ],
                    "post_model_repair_answer_correct": False,
                    "model_repair_accepted": False,
                },
                {
                    "status": "failed",
                    "seed": 2,
                    "problem": "2x = 8",
                    "category": "linear",
                    "expected_answer": "x = 4",
                },
            ],
        }

        summary = run_matched_budget(
            report, model_factory=lambda *args: FakeGlobalModel()
        )

        self.assertEqual(summary["source"]["run_count"], 2)
        self.assertEqual(summary["source"]["completed_count"], 1)
        self.assertEqual(summary["source"]["failure_count"], 1)
        self.assertEqual(summary["strategies"][1]["answer_accuracy"], 0.5)

    def test_reports_zero_budget_when_no_completed_trace_has_an_error(self):
        report = {
            "model": "test-model",
            "temperature": 0.0,
            "model_repair_accept_count": 0,
            "model_repair_attempt_count": 0,
            "results": [
                {
                    "status": "completed",
                    "seed": 1,
                    "temperature": 0.0,
                    "problem": "3x = 9",
                    "category": "linear",
                    "expected_answer": "x = 3",
                    "answer_correct": True,
                    "model_trace_valid": True,
                    "model_repair_attempts": [],
                    "post_model_repair_answer_correct": True,
                },
                {
                    "status": "failed",
                    "seed": 2,
                    "problem": "2x = 8",
                    "category": "linear",
                    "expected_answer": "x = 4",
                },
            ],
        }

        summary = run_matched_budget(report)

        self.assertTrue(summary["matched_budget_comparison_valid"])
        self.assertEqual(summary["source"]["detected_error_runs"], 0)
        self.assertEqual(summary["local_repair_additional_token_budget"], 0)
        self.assertEqual(summary["global_regeneration_additional_tokens"], 0)
        self.assertEqual(summary["global_budget_utilization_rate"], 0.0)
        self.assertEqual(summary["strategies"][0]["answer_accuracy"], 0.5)
        self.assertEqual(summary["strategies"][1]["answer_accuracy"], 0.5)
        self.assertEqual(summary["strategies"][2]["answer_accuracy"], 0.5)
        self.assertEqual(summary["global_regeneration_results"], [])


if __name__ == "__main__":
    unittest.main()
