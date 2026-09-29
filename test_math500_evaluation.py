import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from learned_verifier import load_examples, train_verifier
from math500_evaluation import evaluate_math500, load_checkpoint
from math_answer_scoring import answers_equivalent, extract_final_answer
from rescore_math500 import compact_rescored_result


class FakeTextModel:
    def __init__(self, seed):
        self.seed = seed
        self.last_raw_response = json.dumps({"steps": ["Compute", "Answer: 8"]})
        self.last_metadata = {"prompt_eval_count": 10, "eval_count": 5}
        self.last_repair_raw_response = ""
        self.last_repair_metadata = {}

    def solve(self, problem):
        return ["Compute", "Answer: 8"]

    def repair_text(self, problem, valid_prefix, bad_step, error_type, attempt_index):
        self.last_repair_raw_response = json.dumps({"steps": ["Answer: 9"]})
        self.last_repair_metadata = {"prompt_eval_count": 8, "eval_count": 3}
        return ["Answer: 9"]


class Math500EvaluationTests(unittest.TestCase):
    def test_extracts_and_normalizes_common_math_answers(self):
        self.assertEqual(extract_final_answer([r"Thus $\boxed{\frac{11}{2}}$."]), r"\frac{11}{2}")
        self.assertEqual(
            extract_final_answer([r"The smallest real number is $5.5$."]),
            "5.5",
        )
        self.assertEqual(
            extract_final_answer(["The fraction simplifies to 243 / 625."]),
            "243 / 625",
        )
        self.assertEqual(
            extract_final_answer(
                ["The number of different assortments that can be selected is 28."]
            ),
            "28",
        )
        self.assertEqual(
            extract_final_answer(["h + k + a + b = -3 + 2 + 12 + 5 = 16."]),
            "16",
        )
        pairs = [
            (r"\frac{11}{2}", "5.5"),
            (r"288 \pi", "288*pi"),
            (r"183^\circ", "183 degrees"),
            (r"\$36", "36 dollars"),
            (r"x \in [-2,7]", "[-2, 7]"),
            (r"1+274i", "1 + 274 I"),
            ("8", "3 + 3 + 2 = 8"),
            ("16", "h+k+a+b=-3+2+12+5=16"),
        ]
        for expected, actual in pairs:
            self.assertTrue(answers_equivalent(expected, actual), (expected, actual))
        self.assertFalse(answers_equivalent("8", "9"))

    def test_reports_accuracy_verification_repair_and_cost(self):
        examples = load_examples(Path(__file__).with_name("typed_verifier_pilot.json"))
        verifier, _ = train_verifier(examples, seed=42)
        problem = {
            "benchmark_id": "test/example.json",
            "problem": "How many divisors does 196 have?",
            "answer": "9",
            "subject": "Number Theory",
            "level": 5,
        }
        with TemporaryDirectory() as directory:
            traces = Path(directory) / "traces.jsonl"
            report = evaluate_math500(
                [problem],
                verifier,
                "fake",
                traces,
                model_factory=FakeTextModel,
            )
            trace = json.loads(traces.read_text(encoding="utf-8"))

        self.assertEqual(report["problem_count"], 1)
        self.assertEqual(report["strict_output_contract_rate"], 1.0)
        self.assertEqual(report["initial_answer_accuracy"], 0.0)
        self.assertEqual(report["final_answer_accuracy"], 1.0)
        self.assertEqual(report["repair_success_rate"], 1.0)
        self.assertEqual(report["total_model_calls"], 2)
        self.assertEqual(report["total_tokens"], 26)
        self.assertEqual(trace["reference_answer"], "9")
        self.assertNotIn("9", trace["raw_response"])

    def test_rescores_preserved_repair_output_without_another_model_call(self):
        record = {
            "benchmark_id": "test/example.json",
            "subject": "Algebra",
            "level": 4,
            "status": "completed",
            "reference_answer": r"\frac{11}{2}",
            "initial_steps": ["Final answer: 6"],
            "raw_response": "",
            "predicted_error_location": "n2",
            "repair_attempted": True,
            "repair_generation_succeeded": True,
            "repair_attempts": [
                {
                    "steps": [r"The smallest real number is $5.5$."],
                    "raw_response": "",
                }
            ],
            "strict_output_contract": True,
            "normalized_output_recovery": False,
            "model_call_count": 2,
            "total_tokens": 20,
        }

        result = compact_rescored_result(record)

        self.assertFalse(result["initial_answer_correct"])
        self.assertTrue(result["final_answer_correct"])
        self.assertTrue(result["repair_success"])

    def test_resume_uses_checkpoint_without_repeating_model_call(self):
        examples = load_examples(Path(__file__).with_name("typed_verifier_pilot.json"))
        verifier, _ = train_verifier(examples, seed=42)
        problem = {
            "benchmark_id": "test/resume.json",
            "problem": "How many divisors does 196 have?",
            "answer": "8",
            "subject": "Number Theory",
            "level": 5,
        }
        calls = 0

        def factory(seed):
            nonlocal calls
            calls += 1
            return FakeTextModel(seed)

        with TemporaryDirectory() as directory:
            traces = Path(directory) / "traces.jsonl"
            first = evaluate_math500(
                [problem], verifier, "fake", traces, model_factory=factory, repair_attempts=0
            )
            second = evaluate_math500(
                [problem],
                verifier,
                "fake",
                traces,
                model_factory=factory,
                repair_attempts=0,
                resume=True,
            )
            checkpoint = load_checkpoint(traces)

        self.assertEqual(calls, 1)
        self.assertEqual(first["initial_answer_accuracy"], 1.0)
        self.assertEqual(second["initial_answer_accuracy"], 1.0)
        self.assertEqual(set(checkpoint), {"test/resume.json"})


if __name__ == "__main__":
    unittest.main()
