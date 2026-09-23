import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from error_taxonomy import ERROR_TYPE_CODES
from generate_verifier_dataset import generate_examples, write_dataset
from mathrepair_demo import verify_reasoning_step
from repair_policy import choose_repair_action


class VerifierDatasetGenerationTests(unittest.TestCase):
    def test_generates_balanced_paired_traces(self):
        examples = generate_examples(count_per_type=2, seed=7)

        self.assertEqual(len(examples), 16)
        self.assertEqual(
            {example["error_type"] for example in examples},
            set(ERROR_TYPE_CODES),
        )
        for example in examples:
            required = {
                "correct_trace",
                "corrupted_trace",
                "error_location",
                "error_type",
                "corrupted_step",
                "correct_step",
                "preferred_repair_action",
            }
            self.assertTrue(required.issubset(example))
            self.assertEqual(
                example["preferred_repair_action"],
                choose_repair_action(str(example["error_type"])).value,
            )
            self.assertNotIn("solution", example)
            correct_nodes = {
                node["node_id"]: node for node in example["correct_trace"]
            }
            corrupted_nodes = {
                node["node_id"]: node for node in example["corrupted_trace"]
            }
            location = str(example["error_location"])
            self.assertIn(location, correct_nodes)
            self.assertIn(location, corrupted_nodes)
            self.assertTrue(
                correct_nodes[location] != corrupted_nodes[location]
                or example["corruption_variant"] == "missing_final_isolation"
            )

    def test_generation_is_deterministic_and_manifest_hash_matches(self):
        examples_a = generate_examples(count_per_type=1, seed=11)
        examples_b = generate_examples(count_per_type=1, seed=11)
        self.assertEqual(examples_a, examples_b)

        with TemporaryDirectory() as directory:
            output = Path(directory) / "dataset.json"
            manifest = Path(directory) / "manifest.json"
            write_dataset(output, manifest, examples_a, seed=11)
            records = json.loads(output.read_text(encoding="utf-8"))
            manifest_data = json.loads(manifest.read_text(encoding="utf-8"))

        self.assertEqual(len(records), len(ERROR_TYPE_CODES))
        self.assertEqual(manifest_data["example_count"], len(records))
        self.assertFalse(manifest_data["reference_solution_leakage"])
        self.assertEqual(len(manifest_data["sha256"]), 64)

    def test_symbolic_corruptions_match_their_typed_verifier_labels(self):
        symbolic_types = {
            "arithmetic_error",
            "algebraic_transformation_error",
            "sign_error",
        }
        for example in generate_examples(count_per_type=6, seed=42):
            if example["error_type"] not in symbolic_types:
                continue
            ok, error_type, _, _ = verify_reasoning_step(
                str(example["problem"]), str(example["corrupted_step"])
            )
            self.assertFalse(ok, example["example_id"])
            self.assertEqual(error_type, example["error_type"])

    def test_logical_examples_have_complete_positive_even_divisor_sets(self):
        examples = generate_examples(count_per_type=6, seed=42)
        logical_examples = [
            example
            for example in examples
            if example["error_type"] == "logical_inference_error"
        ]
        for example in logical_examples:
            divisor = int(str(example["problem"]).split()[-1].rstrip("."))
            expected = f"n in {{2, {divisor}}}"
            self.assertIn("positive even divisor", example["problem"])
            self.assertEqual(example["correct_step"], expected)


if __name__ == "__main__":
    unittest.main()
