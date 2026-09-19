import unittest

from local_repair import apply_local_repair
from reasoning_chain import analyze_chain


class LocalRepairTests(unittest.TestCase):
    def test_repairs_algebra_error_and_removes_affected_suffix(self):
        problem = "2(x + 3) = 14"
        steps = ["2x + 3 = 14", "2x = 11", "x = 5.5"]
        analysis = analyze_chain(problem, steps)

        repair = apply_local_repair(problem, steps, analysis)

        self.assertTrue(repair.attempted)
        self.assertTrue(repair.success)
        self.assertEqual(repair.replaced_node_id, "n2")
        self.assertEqual(repair.removed_node_ids, ["n3", "n4"])
        self.assertEqual(repair.repaired_steps, ["2x + 6 = 14", "x = 4"])
        self.assertIsNone(repair.validation.error_node_id)

    def test_repairs_sign_error(self):
        repair = apply_local_repair(
            "x - 5 = 2",
            ["x = 2 - 5", "x = -3"],
        )

        self.assertTrue(repair.success)
        self.assertEqual(repair.repaired_steps, ["x = 7"])

    def test_repairs_supporting_arithmetic_error(self):
        repair = apply_local_repair(
            "5(x + 4) = 45",
            ["x + 4 = 45/5", "45/5 = 8", "x + 4 = 8", "x = 4"],
        )

        self.assertTrue(repair.success)
        self.assertEqual(
            repair.repaired_steps,
            ["x + 4 = 45/5", "45/5 = 9", "x = 5"],
        )

    def test_leaves_a_valid_chain_unchanged(self):
        steps = ["2x + 6 = 14", "2x = 8", "x = 4"]

        repair = apply_local_repair("2(x + 3) = 14", steps)

        self.assertFalse(repair.attempted)
        self.assertTrue(repair.success)
        self.assertEqual(repair.repaired_steps, steps)

    def test_repairs_observed_wrong_nested_distribution_answer(self):
        problem = "7(2(3x - 5) + 4) - 5(x + 9) = 96"
        steps = [
            "42x - 42 - 5x - 45 = 96",
            "37x - 87 = 96",
            "37x = 183",
            "x = 5",
        ]

        repair = apply_local_repair(problem, steps)

        self.assertTrue(repair.success)
        self.assertEqual(repair.replaced_node_id, "n5")
        self.assertEqual(repair.repaired_steps[-1], "x = 183/37")


if __name__ == "__main__":
    unittest.main()
