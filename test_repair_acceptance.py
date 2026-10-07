import inspect
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from learned_verifier import load_examples, train_verifier
from math500_system_ablation import run_arm
from repair_acceptance import compare_repair_states


class RepairAcceptanceTests(unittest.TestCase):
    def test_gate_does_not_take_a_reference_answer(self):
        parameters = inspect.signature(compare_repair_states).parameters

        self.assertNotIn("answer", parameters)
        self.assertNotIn("reference_answer", parameters)
        self.assertNotIn("correct_answer", compare_repair_states.__code__.co_names)

    def test_text_repair_is_rejected_even_when_it_matches_a_known_answer(self):
        decision = compare_repair_states(
            "How many divisors does 196 have?",
            ["Compute", "Answer: 8"],
            ["Compute", "Answer: 9"],
        )

        self.assertFalse(decision.accepted)
        self.assertEqual(decision.original_verification_mode, "text_unverified")
        self.assertEqual(decision.repaired_verification_mode, "text_unverified")

    def test_verified_equation_repair_replaces_a_broken_chain(self):
        decision = compare_repair_states(
            "2(x + 3) = 14",
            ["2x + 3 = 14", "2x = 11", "x = 5.5"],
            ["2x + 6 = 14", "x = 4"],
        )

        self.assertTrue(decision.accepted)

    def test_still_wrong_equation_repair_is_rejected(self):
        decision = compare_repair_states(
            "2(x + 3) = 14",
            ["2x + 3 = 14", "x = 5.5"],
            ["2x + 6 = 14", "x = 5"],
        )

        self.assertFalse(decision.accepted)
        self.assertIn("symbolic error", decision.reason)

    def test_verified_original_is_kept(self):
        decision = compare_repair_states(
            "2(x + 3) = 14",
            ["2x + 6 = 14", "x = 4"],
            ["2(x + 3) = 14", "x = 4"],
        )

        self.assertFalse(decision.accepted)
        self.assertIn("already symbolically verified", decision.reason)

    def test_ablation_accepts_a_repair_the_reference_answer_contradicts(self):
        examples = load_examples(Path(__file__).with_name("typed_verifier_pilot.json"))
        full, _ = train_verifier(examples, seed=42, include_graph=True)
        no_graph, _ = train_verifier(examples, seed=42, include_graph=False)
        problem = {
            "benchmark_id": "algebra/local.json",
            "problem": "2(x + 3) = 14",
            "answer": "999",
            "subject": "Algebra",
            "level": 4,
        }
        baseline = {
            **problem,
            "status": "completed",
            "initial_steps": ["2x + 3 = 14", "2x = 11", "x = 5.5"],
            "raw_response": "",
        }

        class AlgebraRepair:
            def __init__(self, seed, completion_cap):
                self.last_repair_raw_response = ""
                self.last_repair_metadata = {"prompt_eval_count": 2, "eval_count": 2}

            def repair_text(self, problem, valid_prefix, bad_step, error_type, attempt_index):
                return ["2x + 6 = 14", "x = 4"]

        with TemporaryDirectory() as directory:
            arm = run_arm(
                "full_mathrepair",
                [problem],
                {problem["benchmark_id"]: baseline},
                full,
                no_graph,
                "fake",
                Path(directory) / "arm.jsonl",
                seed=42,
                temperature=0.0,
                timeout_seconds=1,
                max_output_tokens=32,
                budget=None,
                model_factory=AlgebraRepair,
            )

        result = arm["results"][0]
        self.assertTrue(result["repair_accepted"])
        self.assertEqual(result["final_answer"], "4")
        self.assertFalse(result["final_answer_correct"])


if __name__ == "__main__":
    unittest.main()
