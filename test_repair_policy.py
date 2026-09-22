import unittest

from repair_policy import RepairAction, choose_repair_action, make_repair_decision


class RepairPolicyTests(unittest.TestCase):
    def test_selects_tool_for_arithmetic(self):
        self.assertEqual(
            choose_repair_action("arithmetic_error"),
            RepairAction.TOOL_EXECUTE,
        )

    def test_selects_backtrack_for_sign_error(self):
        self.assertEqual(
            choose_repair_action("sign_error"),
            RepairAction.BACKTRACK,
        )

    def test_selects_reformalize_for_algebra(self):
        decision = make_repair_decision(
            "algebraic_transformation_error", "2x + 6 = 14"
        )

        self.assertEqual(decision.action, RepairAction.REFORMALIZE)
        self.assertEqual(decision.replacement, "2x + 6 = 14")

    def test_unknown_error_uses_local_resample(self):
        self.assertEqual(
            choose_repair_action("unknown_error"),
            RepairAction.LOCAL_RESAMPLE,
        )

    def test_missing_assumption_uses_backtrack(self):
        self.assertEqual(
            choose_repair_action("missing_assumption"),
            RepairAction.BACKTRACK,
        )

    def test_incomplete_solution_uses_replan(self):
        self.assertEqual(
            choose_repair_action("incomplete_solution"),
            RepairAction.REPLAN,
        )


if __name__ == "__main__":
    unittest.main()
