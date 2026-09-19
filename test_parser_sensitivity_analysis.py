import unittest

from parser_sensitivity_analysis import (
    equation_fragments,
    load_tolerant_steps,
    normalize_sensitivity_equation,
    recover_failed_trace,
)


class ParserSensitivityAnalysisTests(unittest.TestCase):
    def test_loads_unescaped_latex_command_from_model_json(self):
        raw = '{"steps": ["x = \\sqrt{9}"]}'

        self.assertEqual(load_tolerant_steps(raw), [r"x = \sqrt{9}"])

    def test_normalizes_latex_and_prose_without_changing_numbers(self):
        self.assertEqual(
            normalize_sensitivity_equation(
                r"Divide both sides: x = \frac{15}{37}"
            ),
            "x = (15)/(37)",
        )
        self.assertEqual(
            normalize_sensitivity_equation(r"x = \sqrt[3]{729}"),
            "x = ((729)^(1/(3)))",
        )

    def test_splits_chained_equalities(self):
        self.assertEqual(
            equation_fragments("x^2 = 9 = 3^2"),
            ["x^2 = 9", "9 = 3^2"],
        )

    def test_recovers_correct_fraction_answer(self):
        raw = '{"steps": ["19x = 5", "x = \\\\frac{5}{19}"]}'

        result = recover_failed_trace(
            "(4x + 13)/(5x - 6) = -3", "x = 5/19", raw
        )

        self.assertTrue(result["recovered"])
        self.assertTrue(result["trace_valid"])
        self.assertTrue(result["answer_correct"])
        self.assertTrue(result["has_isolated_answer"])

    def test_recovered_wrong_answer_remains_invalid(self):
        raw = '{"steps": ["37x = 13", "x = \\frac{13}{37}"]}'

        result = recover_failed_trace(
            "9(5x + 4) - 4(3x - 7) = 6(x + 8) + 11",
            "x = -5/27",
            raw,
        )

        self.assertTrue(result["recovered"])
        self.assertFalse(result["trace_valid"])
        self.assertFalse(result["answer_correct"])

    def test_unrecoverable_json_is_counted_instead_of_raising(self):
        result = recover_failed_trace(
            "3x = 9",
            "x = 3",
            '{"steps": [\n\n}',
        )

        self.assertFalse(result["recovered"])
        self.assertFalse(result["answer_correct"])
        self.assertEqual(result["error_type"], "unrecoverable_response_format")

    def test_malformed_expression_is_counted_instead_of_raising(self):
        result = recover_failed_trace(
            "2x = 8",
            "x = 4",
            '{"steps": ["x = ((("]}',
        )

        self.assertFalse(result["recovered"])
        self.assertEqual(result["error_type"], "parser_failure")


if __name__ == "__main__":
    unittest.main()
