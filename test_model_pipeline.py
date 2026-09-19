import unittest

from model_pipeline import (
    MockMathModel,
    extract_equation_steps,
    parse_model_steps,
    parse_qwen_json_steps,
    run_pipeline,
    select_model_answer_step,
)
from repair_policy import RepairAction


class ModelPipelineTests(unittest.TestCase):
    def test_parses_strict_model_json(self):
        steps = parse_model_steps('{"steps": ["2x + 6 = 14", "x = 4"]}')

        self.assertEqual(steps, ["2x + 6 = 14", "x = 4"])

    def test_rejects_prose_instead_of_json(self):
        with self.assertRaisesRegex(ValueError, "JSON"):
            parse_model_steps("First, expand the equation.")

    def test_rejects_a_step_without_an_equation(self):
        with self.assertRaisesRegex(ValueError, "equation"):
            parse_model_steps('{"steps": ["Expand the brackets"]}')

    def test_qwen_profile_discards_explanatory_step_entries(self):
        response = (
            '{"steps": ["Expand the parentheses.", '
            '"8x + 6 = 14", "x = 1"]}'
        )

        self.assertEqual(
            parse_qwen_json_steps("8x + 6 = 14", response),
            ["8x + 6 = 14", "x = 1"],
        )

    def test_qwen_profile_accepts_fenced_json_and_latex(self):
        response = '```json\n{"steps": ["x = \\\\frac{8}{2}"]}\n```'

        self.assertEqual(
            parse_qwen_json_steps("2x = 8", response),
            ["x = (8)/(2)"],
        )

    def test_rejects_nonpositive_output_token_cap(self):
        with self.assertRaisesRegex(ValueError, "at least 1"):
            from model_pipeline import OllamaMathModel

            OllamaMathModel("test-model", max_output_tokens=0)

    def test_extracts_equations_from_latex_prose(self):
        response = r"""
        Start with \[2(x + 3) = 14\].
        Expand it:
        \[2x + 6 = 14\]
        Then \[2x = 8\] and finally \[x = 4\].
        """

        self.assertEqual(
            extract_equation_steps(response),
            ["2(x + 3) = 14", "2x + 6 = 14", "2x = 8", "x = 4"],
        )

    def test_converts_simple_latex_fraction(self):
        response = r"Divide both sides: \[\frac{2x}{2} = \frac{8}{2}\]"

        self.assertEqual(
            extract_equation_steps(response),
            ["(2x)/(2) = (8)/(2)"],
        )

    def test_removes_equations_repeated_by_latex_and_line_scans(self):
        response = "Start:\n\\[x + 1 = 2\\]\nAgain: \\[x + 1 = 2\\]"

        self.assertEqual(extract_equation_steps(response), ["x + 1 = 2"])

    def test_filters_coefficient_symbols_not_used_by_problem(self):
        response = r"Coefficients: \(a = 1\), \(b = -10\). Then \(x = 5\)."

        self.assertEqual(
            extract_equation_steps(response, allowed_symbols={"x"}),
            ["x = 5"],
        )

    def test_selects_solution_before_final_numeric_identity(self):
        answer = select_model_answer_step(
            "x^3 = 27",
            ["x^3 = 27", "x = 3", "27 = 3^3"],
        )

        self.assertEqual(answer, "x = 3")

    def test_repeated_original_equation_does_not_override_answer(self):
        answer = select_model_answer_step(
            "(x - 9)^3 = 0",
            ["x - 9 = 0", "x = 9", "(x - 9)^3 = 0"],
        )

        self.assertEqual(answer, "x = 9")

    def test_selects_last_isolated_value_even_when_it_is_wrong(self):
        answer = select_model_answer_step(
            "(5x - 3)/13 - (2x + 7)/17 = 4",
            [
                "59x = 1026",
                "x = 1026/59",
                "x = 17.452542372881356",
                "x = 17 (7)/(59)",
                "(5x - 3)/13 - (2x + 7)/17 = 4",
            ],
        )

        self.assertEqual(answer, "x = 17 (7)/(59)")

    def test_mock_model_runs_through_mathrepair(self):
        result = run_pipeline(
            "2(x + 3) = 14",
            MockMathModel(),
            provider="mock",
            model_name="test-mock",
        )

        self.assertEqual(result.analysis.error_node_id, "n2")
        self.assertEqual(
            result.analysis.error_type,
            "algebraic_transformation_error",
        )
        self.assertEqual(result.decision.action, RepairAction.REFORMALIZE)
        self.assertEqual(result.analysis.correct_answer, "x = 4")
        self.assertTrue(result.repair.success)
        self.assertEqual(result.repair.repaired_steps, ["2x + 6 = 14", "x = 4"])
        self.assertTrue(result.model_repair.accepted)


if __name__ == "__main__":
    unittest.main()
