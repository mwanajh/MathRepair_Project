import tempfile
import unittest
from pathlib import Path
from urllib import error as url_error

from collect_model_traces import (
    answer_signature,
    answers_match,
    is_infrastructure_failure,
    load_problems,
)


class CollectModelTracesTests(unittest.TestCase):
    def test_compares_equivalent_answers(self):
        self.assertTrue(answers_match("x = 4", "2x = 8"))
        self.assertTrue(answers_match("x = 25/4", "4x = 25"))
        self.assertTrue(answers_match("x = -83/8", "x = -10.375"))
        self.assertFalse(answers_match("x = 4", "x = 5"))

    def test_loads_and_limits_problem_csv(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "problems.csv"
            path.write_text(
                "problem,expected_answer,category\n"
                "2x = 8,x = 4,linear\n"
                "3x = 9,x = 3,linear\n",
                encoding="utf-8",
            )

            rows = load_problems(path, limit=1)

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["expected_answer"], "x = 4")

    def test_answer_signature_normalizes_equivalent_steps(self):
        self.assertEqual(
            answer_signature("2x = 8", "x = 4"),
            answer_signature("2x = 8", "2x = 8"),
        )

    def test_answer_signature_normalizes_exact_decimal(self):
        self.assertEqual(
            answer_signature("16x = -166", "x = -83/8"),
            answer_signature("16x = -166", "x = -10.375"),
        )

    def test_identifies_only_transient_infrastructure_failures(self):
        self.assertTrue(is_infrastructure_failure(TimeoutError("timed out")))
        self.assertTrue(
            is_infrastructure_failure(
                url_error.URLError(ConnectionRefusedError("refused"))
            )
        )
        self.assertFalse(is_infrastructure_failure(ValueError("bad math")))
        self.assertFalse(
            is_infrastructure_failure(
                url_error.HTTPError("url", 500, "server", {}, None)
            )
        )


if __name__ == "__main__":
    unittest.main()
