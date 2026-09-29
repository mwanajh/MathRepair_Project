import unittest
from pathlib import Path

from learned_verifier import load_examples
from verifier_ablation import run_ablation


class VerifierAblationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        examples = load_examples(Path(__file__).with_name("typed_verifier_pilot.json"))
        cls.report = run_ablation(examples, seed=42)

    def test_runs_all_requested_variants_on_the_same_test_examples(self):
        self.assertEqual(
            [item["variant_id"] for item in self.report["variants"]],
            ["full_mathrepair", "no_graph", "no_typed_error", "no_symbolic_tool"],
        )
        self.assertEqual(self.report["evaluation_scope"], "verifier_stage_only")
        self.assertEqual(self.report["test_example_count"], 8)

    def test_no_typed_error_does_not_report_type_or_end_to_end_accuracy(self):
        variants = {item["variant_id"]: item for item in self.report["variants"]}
        metrics = variants["no_typed_error"]["metrics"]

        self.assertFalse(metrics["typed_error_available"])
        self.assertIsNone(metrics["error_type_accuracy"])
        self.assertIsNone(metrics["end_to_end_accuracy"])
        self.assertIsNone(metrics["delta_end_to_end_accuracy_pp"])

    def test_metrics_are_bounded(self):
        for variant in self.report["variants"]:
            location = variant["metrics"]["error_location_accuracy"]
            self.assertGreaterEqual(location, 0.0)
            self.assertLessEqual(location, 1.0)


if __name__ == "__main__":
    unittest.main()
