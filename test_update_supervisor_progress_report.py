import unittest

from docx import Document

from update_supervisor_progress_report import UPDATE_HEADING, remove_existing_update


class SupervisorProgressReportTests(unittest.TestCase):
    def test_removes_existing_update_and_every_element_after_it(self):
        document = Document()
        document.add_paragraph("Original report")
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


if __name__ == "__main__":
    unittest.main()
