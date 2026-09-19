import unittest

from model_repair import attempt_model_repair
from reasoning_chain import analyze_chain


class CandidateModel:
    def __init__(self, candidates):
        self.candidates = candidates
        self.last_repair_raw_response = ""
        self.last_repair_metadata = {}
        self.calls = []

    def repair(
        self,
        problem,
        valid_prefix,
        bad_step,
        error_type,
        attempt_index,
    ):
        self.calls.append(
            {
                "valid_prefix": list(valid_prefix),
                "bad_step": bad_step,
                "error_type": error_type,
            }
        )
        candidate = self.candidates[attempt_index - 1]
        self.last_repair_raw_response = str(candidate)
        self.last_repair_metadata = {"attempt": attempt_index}
        return candidate


class ModelRepairTests(unittest.TestCase):
    def setUp(self):
        self.problem = "2(x + 3) = 14"
        self.steps = ["2x + 3 = 14", "2x = 11", "x = 5.5"]
        self.analysis = analyze_chain(self.problem, self.steps)

    def test_accepts_a_verified_model_candidate(self):
        result = attempt_model_repair(
            self.problem,
            self.steps,
            self.analysis,
            CandidateModel([["2x + 6 = 14", "x = 4"]]),
            max_attempts=1,
        )

        self.assertTrue(result.attempted)
        self.assertTrue(result.accepted)
        self.assertEqual(result.repaired_steps, ["2x + 6 = 14", "x = 4"])

    def test_rejects_a_symbolically_wrong_candidate(self):
        result = attempt_model_repair(
            self.problem,
            self.steps,
            self.analysis,
            CandidateModel([["2x + 6 = 14", "x = 5"]]),
            max_attempts=1,
        )

        self.assertFalse(result.accepted)
        self.assertEqual(result.attempts[0].first_error_node, "n3")

    def test_rejects_a_candidate_without_an_isolated_answer(self):
        result = attempt_model_repair(
            self.problem,
            self.steps,
            self.analysis,
            CandidateModel([["2x + 6 = 14"]]),
            max_attempts=1,
        )

        self.assertFalse(result.accepted)
        self.assertIn("isolated", result.attempts[0].rejection_reason)

    def test_can_accept_a_later_attempt(self):
        model = CandidateModel(
            [
                ["2x + 6 = 14", "x = 5"],
                ["2x + 6 = 14", "x = 4"],
            ]
        )
        result = attempt_model_repair(
            self.problem,
            self.steps,
            self.analysis,
            model,
            max_attempts=2,
        )

        self.assertTrue(result.accepted)
        self.assertEqual(len(result.attempts), 2)
        self.assertFalse(result.attempts[0].accepted)
        self.assertTrue(result.attempts[1].accepted)
        self.assertEqual(model.calls[1]["valid_prefix"], ["2x + 6 = 14"])
        self.assertEqual(model.calls[1]["bad_step"], "x = 5")

    def test_keeps_a_verified_answer_and_discards_a_bad_extra_step(self):
        result = attempt_model_repair(
            self.problem,
            self.steps,
            self.analysis,
            CandidateModel(
                [["2x + 6 = 14", "2x = 8", "x = 4", "x = 5"]]
            ),
            max_attempts=1,
        )

        self.assertTrue(result.accepted)
        self.assertEqual(
            result.repaired_steps,
            ["2x + 6 = 14", "2x = 8", "x = 4"],
        )
        self.assertEqual(result.attempts[0].discarded_steps, ["x = 5"])

    def test_trims_a_regenerated_chain_through_the_repeated_parent(self):
        result = attempt_model_repair(
            self.problem,
            ["2x + 6 = 14", "2x = 8", "x = 5"],
            analyze_chain(
                self.problem,
                ["2x + 6 = 14", "2x = 8", "x = 5"],
            ),
            CandidateModel(
                [["2(x + 3) = 14", "2x + 6 = 14", "2x = 8", "x = 4"]]
            ),
            max_attempts=1,
        )

        self.assertTrue(result.accepted)
        self.assertEqual(result.repaired_steps, ["2x + 6 = 14", "2x = 8", "x = 4"])
        self.assertEqual(
            result.attempts[0].ignored_repeated_prefix[-1], "2x = 8"
        )

    def test_continues_from_a_verified_incomplete_candidate(self):
        model = CandidateModel(
            [
                ["2x + 6 = 14", "2x = 8"],
                ["x = 4"],
            ]
        )

        result = attempt_model_repair(
            self.problem,
            self.steps,
            self.analysis,
            model,
            max_attempts=2,
        )

        self.assertTrue(result.accepted)
        self.assertEqual(
            result.repaired_steps,
            ["2x + 6 = 14", "2x = 8", "x = 4"],
        )
        self.assertEqual(
            model.calls[1]["valid_prefix"],
            ["2x + 6 = 14", "2x = 8"],
        )
        self.assertEqual(model.calls[1]["bad_step"], "2x = 8")
        self.assertEqual(model.calls[1]["error_type"], "incomplete_solution")


if __name__ == "__main__":
    unittest.main()
