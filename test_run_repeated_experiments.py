import unittest
import tempfile
from pathlib import Path

from run_repeated_experiments import (
    aggregate_trial_reports,
    check_model_available,
    render_markdown,
    model_slug,
    summarize_values,
    trial_summary,
    validate_problem_set,
)


def make_trial(seed, global_accuracy, local_accuracy):
    return {
        "base_seed": seed,
        "model": "test-model",
        "temperature": 1.4,
        "samples_per_problem": 3,
        "run_count": 36,
        "problem_set": "test.csv",
        "problem_count": 12,
        "problem_set_sha256": "same-hash",
        "matched_budget_comparison_valid": True,
        "strategies": [
            {
                "name": "no_repair",
                "answer_accuracy": 0.8,
                "trace_valid_rate": 0.75,
                "additional_model_calls": 0,
                "additional_tokens": 0,
            },
            {
                "name": "verified_global_regeneration",
                "answer_accuracy": global_accuracy,
                "trace_valid_rate": global_accuracy,
                "additional_model_calls": 8,
                "additional_tokens": 5000,
            },
            {
                "name": "verified_local_repair",
                "answer_accuracy": local_accuracy,
                "trace_valid_rate": local_accuracy - 0.02,
                "additional_model_calls": 7,
                "additional_tokens": 5500,
            },
        ],
    }


class RepeatedExperimentTests(unittest.TestCase):
    def test_summarizes_with_student_t_interval(self):
        metric = summarize_values([0.8, 0.9, 1.0], bounded_rate=True)

        self.assertAlmostEqual(metric["mean"], 0.9)
        self.assertAlmostEqual(metric["sample_standard_deviation"], 0.1)
        self.assertEqual(metric["trial_count"], 3)
        self.assertGreater(metric["confidence_interval"][1], 0.9)

    def test_makes_safe_model_folder_slug(self):
        self.assertEqual(model_slug("qwen2.5:7b-instruct"), "qwen2.5_7b-instruct")
        self.assertEqual(model_slug("  "), "model")

    def test_aggregates_paired_local_minus_global_results(self):
        trials = [
            make_trial(1, 0.85, 0.95),
            make_trial(2, 0.80, 0.90),
            make_trial(3, 0.90, 1.00),
        ]

        summary = aggregate_trial_reports(trials)
        markdown = render_markdown(summary)

        difference = summary["paired_local_minus_global"][
            "answer_accuracy_difference"
        ]
        self.assertAlmostEqual(difference["mean"], 0.1)
        self.assertTrue(summary["all_budget_comparisons_valid"])
        self.assertTrue(difference["confidence_interval"][0] > 0.09)
        self.assertTrue(
            summary["paired_local_minus_global"][
                "answer_advantage_excludes_zero_95"
            ]
        )
        self.assertIn("Repeated-Seed MathRepair Evaluation", markdown)
        self.assertIn("95% Student-t", markdown)

    def test_rejects_trials_with_different_run_counts(self):
        trials = [make_trial(1, 0.85, 0.95), make_trial(2, 0.80, 0.90)]
        trials[1]["run_count"] = 35

        with self.assertRaisesRegex(ValueError, "different run_count"):
            aggregate_trial_reports(trials)

    def test_rejects_trials_with_different_models(self):
        trials = [make_trial(1, 0.85, 0.95), make_trial(2, 0.80, 0.90)]
        trials[1]["model"] = "larger-model"

        with self.assertRaisesRegex(ValueError, "different models"):
            aggregate_trial_reports(trials)

    def test_rejects_trials_with_different_temperatures(self):
        trials = [make_trial(1, 0.85, 0.95), make_trial(2, 0.80, 0.90)]
        trials[1]["temperature"] = 0.8

        with self.assertRaisesRegex(ValueError, "different temperatures"):
            aggregate_trial_reports(trials)

    def test_rejects_incomplete_trial(self):
        repair_report = {
            "model": "test-model",
            "temperature": 1.4,
            "samples_per_problem": 3,
            "run_count": 36,
            "completed_count": 35,
        }
        matched_report = {
            "source": {"model": "test-model", "run_count": 35},
            "matched_budget_comparison_valid": True,
            "global_budget_utilization_rate": 1.0,
            "strategies": [],
        }

        with self.assertRaisesRegex(
            ValueError, r"completed 35 \+ failures 0 != 36"
        ):
            trial_summary(
                60500,
                repair_report,
                matched_report,
                36,
                "test.csv",
                12,
                "hash",
                ["problem"],
                "test-model",
                1.4,
                3,
            )

    def test_accepts_trial_with_accounted_generation_failures(self):
        repair_report = {
            "model": "test-model",
            "temperature": 1.4,
            "samples_per_problem": 1,
            "run_count": 2,
            "completed_count": 1,
            "failure_count": 1,
            "problem_results": {"p1": {}, "p2": {}},
        }
        matched_report = {
            "source": {"model": "test-model", "run_count": 2},
            "matched_budget_comparison_valid": True,
            "global_budget_utilization_rate": 1.0,
            "strategies": [],
        }

        summary = trial_summary(
            60500,
            repair_report,
            matched_report,
            2,
            "test.csv",
            2,
            "hash",
            ["p1", "p2"],
            "test-model",
            1.4,
            1,
        )

        self.assertEqual(summary["completed_count"], 1)
        self.assertEqual(summary["failure_count"], 1)

    def test_validates_expected_answers_before_evaluation(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "problems.csv"
            path.write_text(
                "problem,expected_answer,category\n"
                "2x = 8,x = 4,linear\n",
                encoding="utf-8",
            )

            problems, digest = validate_problem_set(path)

        self.assertEqual(len(problems), 1)
        self.assertEqual(len(digest), 64)

    def test_rejects_wrong_expected_answer(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "problems.csv"
            path.write_text(
                "problem,expected_answer,category\n"
                "2x = 8,x = 5,linear\n",
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "Expected answer"):
                validate_problem_set(path)


if __name__ == "__main__":
    unittest.main()
