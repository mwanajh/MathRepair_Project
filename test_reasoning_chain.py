import unittest

from reasoning_chain import analyze_chain


class AnalyzeChainTests(unittest.TestCase):
    def test_accepts_a_correct_chain(self):
        analysis = analyze_chain(
            "2(x + 3) = 14",
            ["2x + 6 = 14", "2x = 8", "x = 4"],
        )

        self.assertIsNone(analysis.error_node_id)
        self.assertEqual(analysis.correct_answer, "x = 4")
        self.assertEqual(analysis.affected_node_ids, [])

    def test_accepts_an_exact_decimal_equivalent_to_a_fraction(self):
        analysis = analyze_chain(
            "16x = -166",
            ["x = -166/16", "x = -10.375"],
        )

        self.assertIsNone(analysis.error_node_id)
        self.assertEqual(analysis.correct_answer, "x = -83/8")

    def test_finds_first_error_and_downstream_nodes(self):
        analysis = analyze_chain(
            "2(x + 3) = 14",
            ["2x + 3 = 14", "2x = 11", "x = 5.5"],
        )

        self.assertEqual(analysis.error_node_id, "n2")
        self.assertEqual(analysis.error_type, "algebraic_transformation_error")
        self.assertEqual(analysis.suggested_repair, "2x + 6 = 14")
        self.assertEqual(analysis.affected_node_ids, ["n3", "n4"])
        self.assertEqual(analysis.correct_answer, "x = 4")

    def test_finds_error_after_a_valid_step(self):
        analysis = analyze_chain(
            "x - 5 = 2",
            ["x = 2 - 5", "x = -3"],
        )

        self.assertEqual(analysis.error_node_id, "n2")
        self.assertEqual(analysis.error_type, "sign_error")
        self.assertEqual(analysis.suggested_repair, "x = 7")
        self.assertEqual(analysis.affected_node_ids, ["n3"])

    def test_accepts_a_true_supporting_arithmetic_node(self):
        analysis = analyze_chain(
            "5(x + 4) = 45",
            ["x + 4 = 45/5", "45/5 = 9", "x + 4 = 9", "x = 5"],
        )

        self.assertIsNone(analysis.error_node_id)
        self.assertEqual(analysis.correct_answer, "x = 5")

    def test_detects_a_wrong_supporting_arithmetic_node(self):
        analysis = analyze_chain(
            "5(x + 4) = 45",
            ["x + 4 = 45/5", "45/5 = 8", "x + 4 = 8", "x = 4"],
        )

        self.assertEqual(analysis.error_node_id, "n3")
        self.assertEqual(analysis.error_type, "arithmetic_error")
        self.assertEqual(analysis.suggested_repair, "45/5 = 9")

    def test_accepts_supporting_algebraic_identities(self):
        analysis = analyze_chain(
            "3(2x - 5) + 4 = 2(x + 7)",
            [
                "3*2x - 3*5 + 4 = 2*x + 2*7",
                "6x - 15 + 4 = 6x - 11",
                "6x - 11 = 2x + 14",
                "4x = 25",
                "x = 25/4",
            ],
        )

        self.assertIsNone(analysis.error_node_id)
        self.assertEqual(analysis.correct_answer, "x = 25/4")

    def test_rejects_a_false_supporting_algebraic_identity(self):
        analysis = analyze_chain(
            "3(2x - 5) + 4 = 2(x + 7)",
            ["6x - 15 + 4 = 6x - 12", "x = 25/4"],
        )

        self.assertEqual(analysis.error_node_id, "n2")
        self.assertEqual(
            analysis.error_type, "algebraic_transformation_error"
        )


if __name__ == "__main__":
    unittest.main()
