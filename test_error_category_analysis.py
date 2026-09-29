import copy
import unittest

from error_category_analysis import analyze_categories, render_markdown


def source_record(seed, problem, error_type):
    return {
        "seed": seed,
        "problem": problem,
        "status": "completed",
        "first_error_node": "n2",
        "error_type": error_type,
    }


def local_record(seed, problem, accepted, answer_correct):
    return {
        "seed": seed,
        "problem": problem,
        "accepted": accepted,
        "attempts": [
            {"accepted": accepted, "candidate_answer_correct": answer_correct}
        ],
    }


def matched_fixture():
    errors = [
        source_record(1, "arith", "arithmetic_error"),
        source_record(2, "algebra", "algebraic_transformation_error"),
        source_record(3, "sign", "sign_error"),
    ]
    global_results = [
        {
            "seed": 1,
            "problem": "arith",
            "accepted": False,
            "post_global_answer_correct": False,
        },
        {
            "seed": 2,
            "problem": "algebra",
            "accepted": True,
            "post_global_answer_correct": True,
        },
        {
            "seed": 3,
            "problem": "sign",
            "accepted": True,
            "post_global_answer_correct": True,
        },
    ]
    uniform = [
        local_record(1, "arith", False, True),
        local_record(2, "algebra", False, False),
        local_record(3, "sign", False, False),
    ]
    adaptive = [
        local_record(1, "arith", False, True),
        local_record(2, "algebra", True, True),
        local_record(3, "sign", True, True),
    ]
    return {
        "global_regeneration_results": global_results,
        "strategies": [
            {"name": "verified_local_repair_uniform", "budget_records": uniform},
            {"name": "verified_local_repair_adaptive", "budget_records": adaptive},
        ],
    }, {"results": errors}


class ErrorCategoryAnalysisTests(unittest.TestCase):
    def test_compares_strategies_by_category_and_keeps_unobserved_categories(self):
        matched, source = matched_fixture()
        report = analyze_categories(matched, source)
        rows = {row["error_category"]: row for row in report["rows"]}

        self.assertEqual(rows["arithmetic_error"]["observed_error_runs"], 1)
        self.assertEqual(rows["arithmetic_error"]["global_success_rate"], 0.0)
        self.assertEqual(rows["algebraic_transformation_error"]["adaptive_local_success_rate"], 1.0)
        self.assertEqual(rows["sign_error"]["best_observed_strategy"], "tie")
        self.assertIn("missing_assumption", report["unobserved_categories"])
        self.assertIsNone(rows["missing_assumption"]["global_success_rate"])

    def test_markdown_labels_evidence_status_and_limits(self):
        matched, source = matched_fixture()
        markdown = render_markdown(analyze_categories(matched, source))

        self.assertIn("arithmetic_error", markdown)
        self.assertIn("no_observed_cases", markdown)
        self.assertIn("Unobserved categories are not evidence", markdown)


if __name__ == "__main__":
    unittest.main()
