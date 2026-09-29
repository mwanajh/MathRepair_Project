import json
import unittest
from pathlib import Path

from error_taxonomy import ERROR_TYPE_CODES
from learned_verifier import (
    current_rule_baseline,
    evaluate,
    load_examples,
    serialize_node,
    stratified_example_split,
    train_verifier,
)


DATASET = Path(__file__).with_name("typed_verifier_pilot.json")


class LearnedVerifierTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.examples = load_examples(DATASET)
        cls.verifier, cls.split = train_verifier(cls.examples, seed=42)

    def test_split_is_disjoint_and_preserves_every_class(self):
        split = stratified_example_split(self.examples, seed=42)
        id_sets = {
            name: {item["example_id"] for item in items}
            for name, items in split.items()
        }

        self.assertFalse(id_sets["train"] & id_sets["dev"])
        self.assertFalse(id_sets["train"] & id_sets["test"])
        self.assertFalse(id_sets["dev"] & id_sets["test"])
        for items in split.values():
            self.assertEqual({item["error_type"] for item in items}, set(ERROR_TYPE_CODES))
        self.assertEqual([len(split[name]) for name in ("train", "dev", "test")], [32, 8, 8])

    def test_features_do_not_include_clean_trace_or_labels(self):
        example = self.examples[0]
        trace = example["corrupted_trace"]
        text = serialize_node(str(example["problem"]), trace, 0)

        self.assertNotIn("correct_trace", text)
        self.assertNotIn("correct_step", text)
        self.assertNotIn("error_type:", text)
        self.assertNotIn("preferred_repair_action", text)

    def test_predicts_a_frozen_type_and_trace_node(self):
        example = self.split["test"][0]
        prediction = self.verifier.predict(
            str(example["problem"]), list(example["corrupted_trace"])
        )

        node_ids = {node["node_id"] for node in example["corrupted_trace"]}
        self.assertIn(prediction["error_location"], node_ids)
        self.assertIn(prediction["error_type"], ERROR_TYPE_CODES)
        self.assertGreaterEqual(prediction["location_confidence"], 0.0)
        self.assertLessEqual(prediction["location_confidence"], 1.0)

    def test_evaluation_reports_location_type_and_end_to_end_metrics(self):
        metrics = evaluate(self.verifier, self.split["test"])

        self.assertEqual(metrics["example_count"], 8)
        self.assertEqual(
            metrics["confusion_matrix"]["labels"], list(ERROR_TYPE_CODES)
        )
        self.assertEqual(len(metrics["predictions"]), 8)
        for key in (
            "error_location_accuracy",
            "error_type_accuracy",
            "error_type_macro_f1",
            "end_to_end_accuracy",
        ):
            self.assertGreaterEqual(metrics[key], 0.0)
            self.assertLessEqual(metrics[key], 1.0)

    def test_rule_baseline_abstains_on_unparseable_open_math(self):
        result = current_rule_baseline(
            {
                "problem": r"Find $x$ when \frac{x}{2}$ is constrained.",
                "corrupted_trace": [
                    {"node_id": "n1", "state": r"Use \frac{x}{2}", "depends_on": []}
                ],
            }
        )

        self.assertIsNone(result["error_location"])
        self.assertEqual(result["error_type"], "")


if __name__ == "__main__":
    unittest.main()
