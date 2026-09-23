import unittest

from show_experiments import PROJECT_DIR, build_display, table


class ShowExperimentsTests(unittest.TestCase):
    def test_renders_aligned_terminal_table(self):
        rendered = table(
            ["Model", "Accuracy"],
            [["small", "90.0%"], ["larger-model", "80.0%"]],
        )

        lines = rendered.splitlines()
        self.assertEqual(len(lines), 4)
        self.assertTrue(all(len(line) == len(lines[0]) for line in lines))
        self.assertIn("larger-model", rendered)

    def test_rejects_a_row_with_the_wrong_column_count(self):
        with self.assertRaisesRegex(ValueError, "header count"):
            table(["A", "B"], [["only one"]])

    def test_default_display_covers_all_supervisor_tasks(self):
        rendered = build_display("all", PROJECT_DIR)

        for task_number in range(1, 8):
            self.assertIn(f"TASK {task_number} -", rendered)


if __name__ == "__main__":
    unittest.main()
