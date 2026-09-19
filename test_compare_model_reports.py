import unittest

from compare_model_reports import compare_reports, render_markdown, validate_comparable


def make_report(model, temperature=1.4):
    strategies = {}
    for name, answer, trace in (
        ("no_repair", 0.8, 0.75),
        ("verified_global_regeneration", 0.85, 0.85),
        ("verified_local_repair", 0.95, 0.9),
    ):
        strategies[name] = {
            "answer_accuracy": {"mean": answer},
            "trace_valid_rate": {"mean": trace},
        }
    return {
        "model": model,
        "problem_set_sha256": "hash",
        "problem_set": "problems.csv",
        "problem_count": 36,
        "runs_per_trial": 36,
        "temperature": temperature,
        "samples_per_problem": 1,
        "strategy_metrics": strategies,
        "paired_local_minus_global": {},
        "trial_summaries": [{"failure_count": 0}],
    }


class CompareModelReportsTests(unittest.TestCase):
    def test_computes_candidate_minus_baseline_differences(self):
        comparison = compare_reports(make_report("base"), make_report("candidate"))

        self.assertAlmostEqual(
            comparison["strategy_differences"]["no_repair"][
                "answer_accuracy_difference"
            ],
            0.0,
        )
        self.assertEqual(comparison["candidate_model"], "candidate")

    def test_reports_generation_failure_totals(self):
        baseline = make_report("base")
        candidate = make_report("candidate")
        candidate["trial_summaries"] = [
            {"failure_count": 5},
            {"failure_count": 10},
            {"failure_count": 9},
        ]

        comparison = compare_reports(baseline, candidate)

        self.assertEqual(comparison["generation_failures"]["baseline_total"], 0)
        self.assertEqual(comparison["generation_failures"]["candidate_total"], 24)
        self.assertIn("candidate `24`", render_markdown(comparison))

    def test_rejects_different_temperature(self):
        with self.assertRaisesRegex(ValueError, "temperature differs"):
            validate_comparable(make_report("base"), make_report("other", 0.8))


if __name__ == "__main__":
    unittest.main()
