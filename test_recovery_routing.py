import unittest

from learned_verifier import serialize_node
from recovery_routing import (
    ALWAYS_GLOBAL,
    ALWAYS_LOCAL,
    load_routing_examples,
    run_comparison,
    score_actions,
    trace_text,
)


class RecoveryRoutingTests(unittest.TestCase):
    def test_constant_policies_match_only_their_own_action(self):
        expected = ["CONTINUE", "LOCAL_REPAIR", "TOOL_EXECUTE", "REPLAN", "BACKTRACK"]
        labels = list(expected)
        local = score_actions(expected, [ALWAYS_LOCAL] * len(expected), labels)
        global_policy = score_actions(expected, [ALWAYS_GLOBAL] * len(expected), labels)

        self.assertEqual(local["action_accuracy"], 0.2)
        self.assertEqual(global_policy["action_accuracy"], 0.0)

    def test_features_omit_the_recovery_label_and_annotation_note(self):
        examples, observed, unobserved = load_routing_examples()
        example = next(item for item in examples if str(item["example_id"]).endswith("pair-equations/3n"))
        text = trace_text(example)

        self.assertNotIn("recovery_action", text)
        self.assertNotIn("applies n = 4 to both equations", text)
        self.assertNotIn("reference_answer", text)
        serialized = "\n".join(
            serialize_node(str(example["problem"]), list(example["trace"]), index)
            for index in range(len(example["trace"]))
        )
        self.assertNotIn(example["recovery_action"], serialized)
        self.assertEqual(unobserved, ["GLOBAL_REGENERATE"])
        self.assertNotIn("GLOBAL_REGENERATE", observed)
        self.assertEqual(len(examples), 39)

    def test_three_policies_share_one_held_out_split(self):
        report, model = run_comparison(seeds=(42,))

        self.assertIsNotNone(model)
        predictions = {
            name: [row["example_id"] for row in policy["primary_seed_details"]["test_predictions"]]
            for name, policy in report["policies"].items()
        }
        self.assertEqual(len(predictions["learned_tfidf_routing"]), 5)
        self.assertEqual(predictions["always_global_regeneration"], predictions["learned_tfidf_routing"])
        self.assertEqual(predictions["always_local_repair"], predictions["learned_tfidf_routing"])
        learned = report["policies"]["learned_tfidf_routing"]["primary_seed_details"]["test_predictions"]
        observed = set(report["dataset"]["observed_recovery_actions"])
        self.assertTrue(all(row["predicted_action"] in observed for row in learned))
        self.assertEqual(
            report["policies"]["always_global_regeneration"]["full_set_agreement"]["action_accuracy"],
            0.0,
        )


if __name__ == "__main__":
    unittest.main()
