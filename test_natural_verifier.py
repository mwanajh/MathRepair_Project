import json
import unittest

from error_taxonomy import ERROR_TYPE_CODES, VALID_NO_REPAIR
from learned_verifier import load_examples, serialize_node
from learned_verifier import DEFAULT_DATASET
from natural_verifier import (
    _inference_trace,
    load_reviewed_examples,
    run_comparison,
    score_predictions,
)


class NaturalVerifierTests(unittest.TestCase):
    def test_exact_predictions_score_perfect_trigger_and_type_metrics(self):
        examples = []
        predictions = []
        for code in (VALID_NO_REPAIR, *ERROR_TYPE_CODES):
            if code == VALID_NO_REPAIR:
                examples.append({"error_location": None, "error_type": code})
                predictions.append({"error_location": None, "error_type": ""})
            else:
                examples.append({"error_location": "n3", "error_type": code})
                predictions.append({"error_location": "n3", "error_type": code})

        metrics = score_predictions(examples, predictions)

        self.assertEqual(metrics["repair_trigger_precision"], 1.0)
        self.assertEqual(metrics["repair_trigger_recall"], 1.0)
        self.assertEqual(metrics["false_positive_repair_rate"], 0.0)
        self.assertEqual(metrics["error_location_accuracy"], 1.0)
        self.assertEqual(metrics["error_location_f1"], 1.0)
        self.assertEqual(metrics["error_type_macro_f1"], 1.0)

    def test_repairing_a_valid_trace_sets_the_false_positive_rate(self):
        metrics = score_predictions(
            [
                {"error_location": None, "error_type": VALID_NO_REPAIR},
                {"error_location": "n4", "error_type": "dependency_error"},
            ],
            [
                {"error_location": "n2", "error_type": "arithmetic_error"},
                {"error_location": "n4", "error_type": "dependency_error"},
            ],
        )

        self.assertEqual(metrics["repair_trigger_precision"], 0.5)
        self.assertEqual(metrics["repair_trigger_recall"], 1.0)
        self.assertEqual(metrics["false_positive_repair_rate"], 1.0)
        self.assertAlmostEqual(metrics["error_location_f1"], 2 / 3)

    def test_wrong_node_still_counts_as_a_repair_trigger(self):
        metrics = score_predictions(
            [
                {"error_location": None, "error_type": VALID_NO_REPAIR},
                {"error_location": "n4", "error_type": "sign_error"},
            ],
            [
                {"error_location": None, "error_type": ""},
                {"error_location": "n3", "error_type": "sign_error"},
            ],
        )

        self.assertEqual(metrics["repair_trigger_recall"], 1.0)
        self.assertEqual(metrics["false_positive_repair_rate"], 0.0)
        self.assertEqual(metrics["error_location_accuracy"], 0.0)
        self.assertEqual(metrics["error_location_f1"], 0.0)

    def test_abstaining_on_every_trace_has_no_precision(self):
        metrics = score_predictions(
            [
                {"error_location": None, "error_type": VALID_NO_REPAIR},
                {"error_location": "n2", "error_type": "sign_error"},
            ],
            [
                {"error_location": None, "error_type": ""},
                {"error_location": None, "error_type": ""},
            ],
        )

        self.assertIsNone(metrics["repair_trigger_precision"])
        self.assertEqual(metrics["repair_trigger_recall"], 0.0)
        self.assertEqual(metrics["false_positive_repair_rate"], 0.0)

    def test_inference_trace_drops_annotation_fields(self):
        cleaned = _inference_trace(
            [
                {
                    "node_id": "n2",
                    "state": "x = 1",
                    "depends_on": ["n1"],
                    "subgoal": "advance solution",
                    "assumptions": [],
                    "annotation_note": "SECRET_LABEL",
                    "sampling_answer_correct": True,
                }
            ]
        )

        self.assertNotIn("annotation_note", cleaned[0])
        self.assertNotIn("SECRET_LABEL", json.dumps(cleaned))

    def test_reviewed_examples_exclude_labels_that_are_not_features(self):
        examples, statistics, excluded = load_reviewed_examples()

        self.assertTrue(statistics["trainable"])
        self.assertEqual(len(examples), 39)
        self.assertEqual(excluded, ["test/number_theory/1065.json"])
        blob = json.dumps(examples)
        self.assertNotIn("reference_answer", blob)
        self.assertNotIn("sampling_answer_correct", blob)
        self.assertNotIn("annotation_note", blob)
        self.assertNotIn("recovery_action", blob)
        self.assertFalse(
            {item["example_id"] for item in examples}
            & {item["example_id"] for item in load_examples(DEFAULT_DATASET)}
        )
        example = next(
            item for item in examples if item["example_id"] == "math500-pair-equations/3n"
        )
        text = "\n".join(
            serialize_node(str(example["problem"]), list(example["trace"]), index)
            for index in range(len(example["trace"]))
        )
        self.assertNotIn("applies n = 4 to both equations", text)

    def test_comparison_uses_the_same_natural_split_for_every_system(self):
        report, models = run_comparison(seeds=(42,))

        self.assertEqual(set(models), {
            "tfidf_logistic_regression",
            "tfidf_svd_logistic_regression",
        })
        predictions = {
            name: [
                row["example_id"]
                for row in system["primary_seed_details"]["test_predictions"]
            ]
            for name, system in report["systems"].items()
        }
        self.assertEqual(len(predictions["tfidf_logistic_regression"]), 9)
        self.assertEqual(
            predictions["tfidf_logistic_regression"],
            predictions["tfidf_svd_logistic_regression"],
        )
        self.assertEqual(
            predictions["tfidf_logistic_regression"],
            predictions["synthetic_tfidf_baseline"],
        )
        self.assertEqual(
            report["systems"]["synthetic_tfidf_baseline"]["trained_on"],
            "typed_verifier_pilot.json",
        )


if __name__ == "__main__":
    unittest.main()
