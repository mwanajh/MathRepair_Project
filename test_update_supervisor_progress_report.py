import unittest

from docx import Document
from docx.enum.text import WD_BREAK

from update_supervisor_progress_report import (
    UPDATE_HEADING,
    remove_existing_update,
    remove_empty_paragraphs,
    replace_experimental_design_section,
    replace_next_steps_section,
    replace_output_contract_section,
    replace_status_text,
    update_demonstration_section,
    update_implemented_system_table,
)


class SupervisorProgressReportTests(unittest.TestCase):
    def test_removes_existing_update_and_every_element_after_it(self):
        document = Document()
        document.add_paragraph("Original report")
        document.add_paragraph().add_run().add_break(WD_BREAK.PAGE)
        document.add_paragraph().add_run().add_break(WD_BREAK.PAGE)
        document.add_heading(UPDATE_HEADING, level=1)
        document.add_paragraph("Old update")
        document.add_table(rows=1, cols=1).cell(0, 0).text = "Old table"
        document.add_heading(UPDATE_HEADING, level=1)

        remove_existing_update(document)

        self.assertEqual(
            [paragraph.text for paragraph in document.paragraphs],
            ["Original report"],
        )
        self.assertEqual(len(document.tables), 0)

        cleanup_document = Document()
        cleanup_document.add_paragraph("Keep this paragraph")
        cleanup_document.add_paragraph(style="List Bullet")
        cleanup_document.add_paragraph().add_run().add_break(WD_BREAK.PAGE)
        remove_empty_paragraphs(cleanup_document)
        self.assertEqual(
            [paragraph.text for paragraph in cleanup_document.paragraphs],
            ["Keep this paragraph", ""],
        )
        self.assertEqual(
            len(cleanup_document.paragraphs[1]._element.xpath(".//w:br")),
            1,
        )

        document.add_heading("10. Recommended Next Steps", level=1)
        document.add_paragraph("Old recommendation")
        document.add_heading("11. Demonstration Commands", level=1)
        replace_next_steps_section(document)
        text = "\n".join(paragraph.text for paragraph in document.paragraphs)
        self.assertIn("10.1 Completed Supervisor Tasks", text)
        self.assertIn("10.2 Explicitly Deferred Work", text)
        self.assertIn("10.3 Proposed Follow-Up Experiments", text)
        self.assertNotIn("Old recommendation", text)

        design_document = Document()
        design_document.add_heading("5. Experimental Design", level=1)
        design_document.add_table(rows=1, cols=2)
        design_document.add_heading("6. Primary Results", level=1)
        replace_experimental_design_section(design_document)
        design_text = "\n".join(
            paragraph.text for paragraph in design_document.paragraphs
        )
        self.assertIn("5.1 Earlier Expanded Repeated-Seed Evaluation", design_text)
        self.assertIn("5.2 Supervisor Task 1-7 Methodology", design_text)
        self.assertIn("5.3 Interpretation Boundary", design_text)
        self.assertIn("6. Earlier Expanded Evaluation Results", design_text)
        self.assertEqual(len(design_document.tables), 2)

        system_document = Document()
        system_table = system_document.add_table(rows=1, cols=2)
        system_table.rows[0].cells[0].text = "Component"
        system_table.rows[0].cells[1].text = "Implemented capability"
        update_implemented_system_table(system_document)
        components = [row.cells[0].text for row in system_table.rows]
        self.assertIn("Typed-error taxonomy", components)
        self.assertIn("Experiment evidence", components)

        contract_document = Document()
        contract_document.add_heading("7. Model and Output-Contract Findings", level=1)
        contract_document.add_table(rows=1, cols=2)
        contract_document.add_heading("8. Completed Deliverables", level=1)
        replace_output_contract_section(contract_document)
        contract_text = "\n".join(
            paragraph.text for paragraph in contract_document.paragraphs
        )
        self.assertIn("7.1 Strict End-to-End Model Comparison", contract_text)
        self.assertIn("7.2 Parser-Normalized Sensitivity", contract_text)
        self.assertEqual(len(contract_document.tables), 2)

        wording_document = Document()
        wording_document.add_paragraph(
            "The result has a 95% Candidate Interval of [+3.4, +11.4]."
        )
        replace_status_text(wording_document)
        self.assertIn(
            "95% confidence interval",
            wording_document.paragraphs[0].text,
        )

        demo_document = Document()
        demo_document.add_heading("11. Demonstration Commands", level=1)
        demo_document.add_paragraph("python graph_web_server.py --port 8765")
        update_demonstration_section(demo_document)
        update_demonstration_section(demo_document)
        demo_text = "\n".join(
            paragraph.text for paragraph in demo_document.paragraphs
        )
        self.assertEqual(demo_text.count("Primary Tasks 1-7"), 1)
        self.assertEqual(demo_text.count("Live graph-integrated model trace"), 1)


if __name__ == "__main__":
    unittest.main()
