import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from learned_verifier import load_examples, train_verifier
from math500_system_ablation import run_system_ablation


class FakeRepairModel:
    def __init__(self, seed, completion_cap):
        self.last_repair_raw_response = ""
        self.last_repair_metadata = {}

    def repair_text(self, problem, valid_prefix, bad_step, error_type, attempt_index):
        self.last_repair_raw_response = json.dumps({"steps": ["Answer: 9"]})
        self.last_repair_metadata = {"prompt_eval_count": 5, "eval_count": 3}
        return ["Answer: 9"]


class Math500SystemAblationTests(unittest.TestCase):
    def test_runs_requested_system_variants_under_full_arm_budget(self):
        examples = load_examples(Path(__file__).with_name("typed_verifier_pilot.json"))
        full, _ = train_verifier(examples, seed=42, include_graph=True)
        no_graph, _ = train_verifier(examples, seed=42, include_graph=False)
        problem = {
            "benchmark_id": "test/example.json",
            "problem": "How many divisors does 196 have?",
            "answer": "9",
            "subject": "Number Theory",
            "level": 5,
        }
        baseline = {
            **problem,
            "status": "completed",
            "initial_steps": ["Compute", "Answer: 8"],
            "raw_response": json.dumps({"steps": ["Compute", "Answer: 8"]}),
        }
        with TemporaryDirectory() as directory:
            report = run_system_ablation(
                [problem],
                [baseline],
                full,
                no_graph,
                "fake",
                Path(directory) / "arm",
                model_factory=FakeRepairModel,
            )

        self.assertEqual(
            [item["variant_id"] for item in report["variants"]],
            ["full_mathrepair", "no_graph", "no_typed_error", "no_symbolic_tool"],
        )
        self.assertTrue(report["matched_budget_comparison_valid"])
        self.assertEqual(report["matched_additional_token_budget"], 8)
        for arm in report["variants"]:
            result = arm["results"][0]
            self.assertEqual(result["final_answer"], result["initial_answer"])
            self.assertFalse(result["repair_accepted"])
            self.assertEqual(arm["final_answer_accuracy"], arm["initial_answer_accuracy"])
            self.assertEqual(arm["repair_success_rate"], 0.0)
            self.assertLessEqual(arm["additional_tokens"], 8)


if __name__ == "__main__":
    unittest.main()
