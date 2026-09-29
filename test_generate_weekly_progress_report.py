import unittest

from generate_weekly_progress_report import build_document


class WeeklyProgressReportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.document = build_document()
        cls.text = "\n".join(
            [paragraph.text for paragraph in cls.document.paragraphs]
            + [
                cell.text
                for table in cls.document.tables
                for row in table.rows
                for cell in row.cells
            ]
        )

    def test_contains_the_three_requested_focus_areas(self):
        self.assertIn("Learned Typed Verifier", self.text)
        self.assertIn("Full MATH-500 Hard-Subset Evaluation", self.text)
        self.assertIn("Matched-Budget System Ablations", self.text)
        self.assertIn("Supervisor comment addressed", self.text)
        self.assertIn("Error-Category Analysis", self.text)
        self.assertIn("Category-level finding", self.text)
        self.assertIn("Supervisor Deliverable Checklist", self.text)
        self.assertIn("What currently works", self.text)

    def test_contains_current_report_metrics_and_limitations(self):
        for value in (
            "10.0%",
            "5.0%",
            "28,791",
            "8,487",
            "144/144 tests passing",
            "does not establish generalization",
            "not that symbolic support has no value",
        ):
            self.assertIn(value, self.text)

    def test_embeds_one_result_figure_and_expected_tables(self):
        self.assertEqual(len(self.document.inline_shapes), 1)
        self.assertGreaterEqual(len(self.document.tables), 10)
        self.assertEqual(
            self.document.core_properties.title,
            "MathRepair Weekly Research Progress Update",
        )


if __name__ == "__main__":
    unittest.main()
