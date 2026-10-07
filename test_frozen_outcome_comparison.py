import unittest

from frozen_outcome_comparison import (
    apply_policy,
    category_outcomes,
    choose_action,
    run_comparison,
)


class OutcomeComparisonTests(unittest.TestCase):
    def test_valid_trace_is_not_repaired_by_any_policy(self):
        prediction = {"error_location": None, "error_type": ""}

        self.assertEqual(choose_action("always_global_regeneration", prediction, None), "CONTINUE")
        self.assertEqual(choose_action("always_local_repair", prediction, None), "CONTINUE")
        self.assertEqual(choose_action("learned_routing", prediction, "LOCAL_REPAIR"), "CONTINUE")

    def test_text_gate_keeps_the_original_answer(self):
        class TextModel:
            def solve(self, problem):
                return ["Count the divisors.", "Answer: 9"]

            def repair_text(self, problem, prefix, bad_step, error_type, attempt):
                return ["Answer: 9"]

        outcome = apply_policy(
            policy="always_global_regeneration",
            problem="How many divisors does 196 have?",
            steps=["Count the divisors.", "Answer: 8"],
            reference_answer="9",
            prediction={"error_location": "n2", "error_type": "arithmetic_error"},
            routed_action=None,
            model=TextModel(),
        )

        self.assertFalse(outcome["repair_accepted"])
        self.assertEqual(outcome["final_answer"], "8")
        self.assertFalse(outcome["final_answer_correct"])
        self.assertTrue(outcome["candidate_answer_correct"])

    def test_symbolic_gate_accepts_without_using_the_reference(self):
        class AlgebraModel:
            def solve(self, problem):
                raise AssertionError("Global regeneration was not requested.")

            def repair_text(self, problem, prefix, bad_step, error_type, attempt):
                self.seen = (problem, prefix, bad_step, error_type)
                return ["2x + 6 = 14", "x = 4"]

        model = AlgebraModel()
        outcome = apply_policy(
            policy="always_local_repair",
            problem="2(x + 3) = 14",
            steps=["2x + 3 = 14", "2x = 11", "x = 5.5"],
            reference_answer="999",
            prediction={"error_location": "n2", "error_type": "algebraic_transformation_error"},
            routed_action=None,
            model=model,
        )

        self.assertNotIn("999", model.seen)
        self.assertTrue(outcome["repair_accepted"])
        self.assertEqual(outcome["final_answer"], "4")
        self.assertFalse(outcome["final_answer_correct"])

    def test_sparse_category_does_not_name_a_strategy(self):
        rows = []
        for index in range(2):
            for policy in (
                "always_global_regeneration",
                "always_local_repair",
                "learned_routing",
            ):
                rows.append(
                    {
                        "benchmark_id": f"sparse/{index}",
                        "policy": policy,
                        "status": "completed",
                        "predicted_error_location": "n2",
                        "predicted_error_type": "sign_error",
                        "initial_answer_correct": False,
                        "final_answer_correct": policy == "always_local_repair",
                        "repair_accepted": True,
                    }
                )
        sign = next(row for row in category_outcomes(rows) if row["error_category"] == "sign_error")

        self.assertEqual(sign["evidence_status"], "sparse")
        self.assertIsNone(sign["best_observed_strategy"])

    def test_three_traces_can_name_one_strategy(self):
        rows = []
        for index in range(3):
            for policy, corrected in (
                ("always_global_regeneration", False),
                ("always_local_repair", True),
                ("learned_routing", False),
            ):
                rows.append(
                    {
                        "benchmark_id": f"algebra/{index}",
                        "policy": policy,
                        "status": "completed",
                        "predicted_error_location": "n2",
                        "predicted_error_type": "algebraic_transformation_error",
                        "initial_answer_correct": False,
                        "final_answer_correct": corrected,
                        "repair_accepted": True,
                    }
                )
        algebraic = next(
            row
            for row in category_outcomes(rows)
            if row["error_category"] == "algebraic_transformation_error"
        )

        self.assertEqual(algebraic["evidence_status"], "counted")
        self.assertEqual(algebraic["best_observed_strategy"], "always_local_repair")

    def test_backtrack_repairs_from_the_earlier_step(self):
        class RecordingModel:
            def solve(self, problem):
                raise AssertionError("Backtrack does not regenerate the whole trace.")

            def repair_text(self, problem, prefix, bad_step, error_type, attempt):
                self.prefix = prefix
                self.bad_step = bad_step
                return ["2x + 6 = 14", "x = 4"]

        model = RecordingModel()
        outcome = apply_policy(
            policy="learned_routing",
            problem="2(x + 3) = 14",
            steps=["2x + 3 = 14", "2x = 11", "x = 5.5"],
            reference_answer="4",
            prediction={"error_location": "n3", "error_type": "algebraic_transformation_error"},
            routed_action="BACKTRACK",
            model=model,
        )

        self.assertEqual(outcome["action"], "BACKTRACK")
        self.assertEqual(model.prefix, [])
        self.assertEqual(model.bad_step, "2x + 3 = 14")
        self.assertTrue(outcome["repair_accepted"])
        self.assertTrue(outcome["final_answer_correct"])

    def test_router_continue_does_not_generate(self):
        class GuardModel:
            def __init__(self):
                self.calls = []

            def solve(self, problem):
                self.calls.append("solve")
                return ["Count the divisors.", "Answer: 9"]

            def repair_text(self, problem, prefix, bad_step, error_type, attempt):
                self.calls.append("repair")
                return ["Answer: 9"]

        class Verifier:
            def predict(self, problem, trace):
                return {"error_location": "n2", "error_type": "arithmetic_error"}

        class Router:
            def predict(self, texts):
                return ["CONTINUE"]

        model = GuardModel()
        report = run_comparison(
            [
                {
                    "benchmark_id": "text/1",
                    "problem": "How many divisors does 196 have?",
                    "answer": "9",
                    "subject": "Number Theory",
                    "level": 4,
                }
            ],
            {
                "text/1": {
                    "status": "completed",
                    "initial_steps": ["Count the divisors.", "Answer: 8"],
                }
            },
            Verifier(),
            Router(),
            lambda seed: model,
        )
        routed = next(
            row for row in report["results"] if row["policy"] == "learned_routing"
        )

        self.assertEqual(routed["action"], "CONTINUE")
        self.assertFalse(routed["repair_attempted"])
        self.assertEqual(model.calls, ["solve", "repair"])


if __name__ == "__main__":
    unittest.main()
