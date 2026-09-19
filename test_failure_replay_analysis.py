import tempfile
import unittest
from pathlib import Path

from failure_replay_analysis import replay_directory, render_markdown


class FailureReplayAnalysisTests(unittest.TestCase):
    def test_replays_completed_and_failed_runs_by_category(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            trial = root / "seed_1"
            trial.mkdir()
            report = {
                "results": [
                    {
                        "problem": "2x = 8",
                        "seed": 1,
                        "category": "linear",
                        "status": "completed",
                        "answer_correct": True,
                        "model_trace_valid": True,
                        "post_model_repair_answer_correct": True,
                        "post_model_repair_trace_valid": True,
                    },
                    {
                        "problem": "3x = 9",
                        "seed": 2,
                        "category": "linear",
                        "status": "failed",
                        "expected_answer": "x = 3",
                    },
                ]
            }
            (trial / "repair_report.json").write_text(
                __import__("json").dumps(report), encoding="utf-8"
            )
            (trial / "traces.jsonl").write_text(
                '{"status":"failed","problem":"3x = 9",'
                '"raw_response":"{\\"steps\\": [\\"x = 3\\"]}",'
                '"labels":{"seed":"2","expected_answer":"x = 3"}}\n',
                encoding="utf-8",
            )

            result = replay_directory(root)
            metrics = result["categories"]["linear"]

        self.assertEqual(metrics["planned"], 2)
        self.assertEqual(metrics["generation_failures"], 1)
        self.assertEqual(metrics["normalized_answer_correct"], 1)
        self.assertIn("Failure Replay By Category", render_markdown(result))


if __name__ == "__main__":
    unittest.main()
