import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from model_pipeline import (
    MockMathModel,
    extract_equation_steps,
    parse_model_steps,
    parse_qwen_json_steps,
    parse_text_steps,
    run_pipeline,
    save_trace,
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

    def test_parses_open_ended_text_reasoning_steps(self):
        self.assertEqual(
            parse_text_steps('{"steps": ["Count the cases", "Answer: 9"]}'),
            ["Count the cases", "Answer: 9"],
        )

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

    def test_model_trace_is_the_verified_reasoning_graph(self):
        result = run_pipeline(
            "2(x + 3) = 14",
            MockMathModel(),
            provider="mock",
            model_name="test-mock",
        )

        self.assertIs(result.reasoning_graph, result.analysis.nodes)
        error_node = next(
            node for node in result.reasoning_graph if node.node_id == "n2"
        )
        self.assertEqual(error_node.depends_on, ["n1"])
        self.assertEqual(error_node.model_reasoning, "2x + 3 = 14")
        self.assertFalse(error_node.verification_result)
        self.assertEqual(error_node.error_type, "algebraic_transformation_error")
        self.assertEqual(error_node.affected_descendants, ["n3", "n4"])
        self.assertEqual(error_node.repair_action, "REFORMALIZE")
        self.assertEqual(error_node.repaired_state, "2x + 6 = 14")
        self.assertEqual(error_node.final_status, "repaired")
        self.assertEqual(
            next(node for node in result.reasoning_graph if node.node_id == "n3").final_status,
            "recomputed",
        )

    def test_saved_trace_contains_node_level_graph_record(self):
        result = run_pipeline(
            "2(x + 3) = 14",
            MockMathModel(),
            provider="mock",
            model_name="test-mock",
        )
        with TemporaryDirectory() as directory:
            trace_path = Path(directory) / "trace.jsonl"
            save_trace(trace_path, result)
            record = json.loads(trace_path.read_text(encoding="utf-8"))

        self.assertEqual(len(record["reasoning_graph"]), 4)
        self.assertEqual(
            set(record["reasoning_graph"][1]),
            {
                "node_id",
                "subgoal",
                "reasoning_state",
                "parent_dependency",
                "model_generated_reasoning",
                "verification_result",
                "error_type",
                "affected_descendants",
                "repair_action",
                "repaired_state",
                "final_status",
            },
        )

    def test_repair_states_align_with_a_late_graph_error(self):
        class LateErrorModel(MockMathModel):
            def solve(self, problem):
                return ["2x + 6 = 14", "2x = 11", "x = 5.5"]

        result = run_pipeline(
            "2(x + 3) = 14",
            LateErrorModel(),
            provider="mock",
            model_name="late-error-mock",
        )

        self.assertEqual(result.analysis.error_node_id, "n3")
        node_by_id = {node.node_id: node for node in result.reasoning_graph}
        self.assertEqual(node_by_id["n2"].final_status, "verified")
        self.assertEqual(node_by_id["n3"].repaired_state, "2x + 6 = 14")
        self.assertEqual(node_by_id["n3"].final_status, "repaired")
        self.assertEqual(node_by_id["n4"].repaired_state, "x = 4")


if __name__ == "__main__":
    unittest.main()
