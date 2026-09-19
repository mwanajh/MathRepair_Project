import unittest

from category_analysis import category_trial_metrics


class CategoryAnalysisTests(unittest.TestCase):
    def test_reconstructs_global_metrics_for_clean_and_error_runs(self):
        repair = {
            "results": [
                {
                    "problem": "a",
                    "seed": 1,
                    "category": "linear",
                    "status": "completed",
                    "answer_correct": False,
                    "model_trace_valid": False,
                    "post_model_repair_answer_correct": True,
                    "post_model_repair_trace_valid": True,
                },
                {
                    "problem": "b",
                    "seed": 2,
                    "category": "linear",
                    "status": "completed",
                    "answer_correct": True,
                    "model_trace_valid": True,
                    "post_model_repair_answer_correct": True,
                    "post_model_repair_trace_valid": True,
                },
            ]
        }
        matched = {
            "global_regeneration_results": [
                {
                    "problem": "a",
                    "seed": 1,
                    "post_global_answer_correct": True,
                    "post_global_trace_valid": True,
                }
            ]
        }

        metrics = category_trial_metrics(repair, matched)["linear"]

        self.assertEqual(metrics["runs"], 2)
        self.assertEqual(metrics["baseline_answer_correct"], 1)
        self.assertEqual(metrics["global_answer_correct"], 2)
        self.assertEqual(metrics["local_answer_correct"], 2)

    def test_keeps_generation_failures_in_category_denominator(self):
        repair = {
            "results": [
                {
                    "problem": "a",
                    "seed": 1,
                    "category": "cubic",
                    "status": "completed",
                    "answer_correct": True,
                    "model_trace_valid": True,
                },
                {
                    "problem": "b",
                    "seed": 2,
                    "category": "cubic",
                    "status": "failed",
                },
            ]
        }

        metrics = category_trial_metrics(repair, {})["cubic"]

        self.assertEqual(metrics["runs"], 2)
        self.assertEqual(metrics["baseline_answer_correct"], 1)
        self.assertEqual(metrics["baseline_trace_valid"], 1)


if __name__ == "__main__":
    unittest.main()
