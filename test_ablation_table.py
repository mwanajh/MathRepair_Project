import copy
import unittest

from ablation_table import METRIC_KEYS, build_ablation_table, render_markdown


def strategy(name: str, accuracy: float) -> dict[str, object]:
    return {
        "name": name,
        "answer_accuracy": accuracy,
        "trace_valid_rate": accuracy - 0.05,
        "repair_success_rate": 0.5,
        "average_model_calls": 1.25,
        "average_tokens": 700.0,
        "total_compute_cost": 25200,
    }


def valid_matched_report() -> dict[str, object]:
    return {
        "matched_budget_comparison_valid": True,
        "local_evaluation_mode": "live",
        "matched_additional_token_budget": 5800,
        "source": {
            "model": "test-model",
            "run_count": 36,
            "detected_error_runs": 7,
        },
        "strategies": [
            strategy("verified_global_regeneration", 0.89),
            strategy("verified_local_repair_uniform", 0.86),
            strategy("verified_local_repair_adaptive", 0.87),
        ],
    }


class AblationTableTests(unittest.TestCase):
    def test_has_exactly_the_six_frozen_variants(self):
        report = build_ablation_table(valid_matched_report())
        rows = report["rows"]

        self.assertEqual(
            [row["variant_id"] for row in rows],
            [
                "full_mathrepair",
                "no_graph",
                "no_typed_error",
                "no_adaptive_compute",
                "global_instead_of_local",
                "no_symbolic_tool",
            ],
        )
        self.assertEqual(report["completion"]["row_count"], 6)
        self.assertEqual(report["completion"]["measured_count"], 2)
        self.assertEqual(report["completion"]["proxy_count"], 1)
        self.assertEqual(report["completion"]["planned_count"], 3)

    def test_maps_available_results_to_the_correct_variants(self):
        rows = {
            row["variant_id"]: row
            for row in build_ablation_table(valid_matched_report())["rows"]
        }

        self.assertEqual(
            rows["full_mathrepair"]["result_source"],
            "verified_local_repair_adaptive",
        )
        self.assertEqual(rows["full_mathrepair"]["status"], "proxy_result")
        self.assertEqual(
            rows["no_adaptive_compute"]["result_source"],
            "verified_local_repair_uniform",
        )
        self.assertEqual(
            rows["global_instead_of_local"]["result_source"],
            "verified_global_regeneration",
        )
        self.assertAlmostEqual(
            rows["no_adaptive_compute"]["delta_answer_accuracy_pp"], -1.0
        )
        self.assertAlmostEqual(
            rows["global_instead_of_local"]["delta_answer_accuracy_pp"], 2.0
        )

    def test_unfinished_rows_have_only_null_metrics(self):
        rows = build_ablation_table(valid_matched_report())["rows"]
        unfinished = [
            row
            for row in rows
            if row["status"] not in {"measured", "proxy_result"}
        ]

        self.assertEqual(len(unfinished), 3)
        for row in unfinished:
            self.assertEqual(set(row["metrics"]), set(METRIC_KEYS))
            self.assertTrue(all(value is None for value in row["metrics"].values()))

    def test_rejects_invalid_or_replay_only_source_reports(self):
        invalid = valid_matched_report()
        invalid["matched_budget_comparison_valid"] = False
        with self.assertRaisesRegex(ValueError, "not valid"):
            build_ablation_table(invalid)

        replay = copy.deepcopy(valid_matched_report())
        replay["local_evaluation_mode"] = "replay"
        with self.assertRaisesRegex(ValueError, "fresh-call"):
            build_ablation_table(replay)

    def test_markdown_includes_every_variant_and_proxy_warning(self):
        report = build_ablation_table(valid_matched_report())
        markdown = render_markdown(report)

        for row in report["rows"]:
            self.assertIn(f"| {row['variant']} |", markdown)
        self.assertIn("rule-based proxy", markdown)
        self.assertIn("Only rows marked measured", markdown)
        self.assertNotIn("-- tokens", markdown)


if __name__ == "__main__":
    unittest.main()
