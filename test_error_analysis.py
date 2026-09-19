import tempfile
import unittest
from pathlib import Path
import json

from error_analysis import collect_error_metrics, render_markdown


class ErrorAnalysisTests(unittest.TestCase):
    def test_aggregates_typed_error_outcomes(self):
        with tempfile.TemporaryDirectory() as directory:
            trial = Path(directory) / "seed_1"
            trial.mkdir()
            (trial / "repair_report.json").write_text(
                json.dumps(
                    {
                        "results": [
                            {
                                "status": "completed",
                                "model_trace_valid": False,
                                "error_type": "sign_error",
                                "model_repair_accepted": True,
                                "answer_correct": False,
                                "post_model_repair_answer_correct": True,
                            },
                            {
                                "status": "completed",
                                "model_trace_valid": True,
                                "error_type": "sign_error",
                            },
                        ]
                    }
                ),
                encoding="utf-8",
            )

            metrics = collect_error_metrics(Path(directory))

        self.assertEqual(metrics["sign_error"]["detected"], 1)
        self.assertEqual(metrics["sign_error"]["accepted_repairs"], 1)
        self.assertEqual(metrics["sign_error"]["corrected_wrong_answers"], 1)
        self.assertIn("Typed Error Analysis", render_markdown(metrics, Path("x")))


if __name__ == "__main__":
    unittest.main()
