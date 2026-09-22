import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from benchmark_pilot import load_pilot, run_pilot
from prepare_math500_pilot import select_pilot, write_pilot


def make_row(subject: str, index: int, level: int = 4) -> dict[str, object]:
    return {
        "problem": f"Problem {subject} {index}",
        "answer": str(index),
        "subject": subject,
        "level": level,
        "unique_id": f"test/{subject.lower().replace(' ', '_')}/{index}.json",
    }


class BenchmarkPilotTests(unittest.TestCase):
    def test_selects_configured_level_four_five_subject_quotas(self):
        quotas = {"Algebra": 2, "Geometry": 1}
        rows = [
            make_row("Algebra", index, level=4)
            for index in range(4, 1, -1)
        ] + [
            make_row("Geometry", index, level=5)
            for index in range(3, 0, -1)
        ] + [make_row("Algebra", 99, level=3)]

        selected = select_pilot(rows, quotas=quotas)

        self.assertEqual(len(selected), 3)
        self.assertEqual(
            [item["benchmark_id"] for item in selected],
            ["test/algebra/2.json", "test/algebra/3.json", "test/geometry/1.json"],
        )
        self.assertTrue(all(int(item["level"]) >= 4 for item in selected))

    def test_writes_and_loads_pilot_without_reference_solutions(self):
        records = select_pilot(
            [make_row("Algebra", index) for index in range(1, 3)],
            quotas={"Algebra": 2},
        )
        with TemporaryDirectory() as directory:
            output = Path(directory) / "pilot.json"
            manifest = Path(directory) / "manifest.json"
            write_pilot(output, manifest, records)
            loaded = load_pilot(output, limit=None)
            manifest_data = json.loads(manifest.read_text(encoding="utf-8"))

        self.assertEqual(len(loaded), 2)
        self.assertEqual(manifest_data["problem_count"], 2)
        self.assertFalse(manifest_data["reference_solutions_included"])
        self.assertNotIn("solution", loaded[0])

    def test_mock_pilot_uses_text_mode_graph_pipeline(self):
        record = {
            "benchmark": "MATH-500",
            "benchmark_id": "test/algebra/example.json",
            "problem": "How many divisors does 196 have?",
            "answer": "9",
            "subject": "Number Theory",
            "level": 5,
        }
        with TemporaryDirectory() as directory:
            trace_path = Path(directory) / "traces.jsonl"
            results = run_pilot([record], "mock", "offline", trace_path)
            trace = json.loads(trace_path.read_text(encoding="utf-8"))

        self.assertEqual(results[0]["verification_mode"], "text_unverified")
        self.assertEqual(results[0]["graph_node_count"], 3)
        self.assertEqual(trace["labels"]["benchmark_id"], record["benchmark_id"])
        self.assertEqual(trace["verification_mode"], "text_unverified")
        self.assertEqual(trace["reasoning_graph"][-1]["final_status"], "unverified")


if __name__ == "__main__":
    unittest.main()
