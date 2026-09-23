import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from output_contract_evidence import build_evidence


class OutputContractEvidenceTests(unittest.TestCase):
    def make_fixture(self, root: Path) -> tuple[dict[str, str], dict[str, dict[str, object]]]:
        experiment_dir = root / "experiment"
        trace_dir = experiment_dir / "seed_10"
        trace_dir.mkdir(parents=True)
        aggregate = {
            "model": "test-model:1b",
            "prompt_profile": "default",
            "trial_count": 1,
            "runs_per_trial": 2,
            "base_seeds": [10],
            "trial_summaries": [{"failure_count": 1}],
            "strategy_metrics": {
                "no_repair": {"answer_accuracy": {"mean": 0.5}}
            },
        }
        sensitivity = {
            "total_runs": 2,
            "strict_failure_count": 1,
            "mean_normalized_answer_accuracy": 1.0,
        }
        records = [
            {
                "status": "completed",
                "problem": "x = 1",
                "raw_response": '{"steps": ["x = 1"]}',
                "generation_metadata": {},
                "labels": {"seed": "10", "category": "linear"},
            },
            {
                "status": "failed",
                "problem": "x = 2",
                "raw_response": "not json",
                "failure": "parse failure",
                "generation_metadata": {},
                "labels": {"seed": "1010", "category": "linear"},
            },
        ]
        (experiment_dir / "aggregate_report.json").write_text(
            json.dumps(aggregate), encoding="utf-8"
        )
        (experiment_dir / "parser_sensitivity_report.json").write_text(
            json.dumps(sensitivity), encoding="utf-8"
        )
        (trace_dir / "traces.jsonl").write_text(
            "".join(json.dumps(record) + "\n" for record in records),
            encoding="utf-8",
        )
        config = {
            "experiment_id": "test_default",
            "directory": "experiment",
            "model": "test-model:1b",
            "prompt_profile": "default",
        }
        models = {
            "test-model:1b": {
                "ollama_tag": "test-model:1b",
                "digest": "abc123",
            }
        }
        return config, models

    def test_archives_versions_raw_outputs_failures_and_accuracy(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            config, models = self.make_fixture(root)

            manifest, raw_archive = build_evidence(root, [config], models)

        row = manifest["experiments"][0]
        self.assertEqual(row["prompt_version"], "equation_json_default_v1")
        self.assertEqual(row["primary_parser_version"], "equation_parser_default_v1")
        self.assertEqual(row["model_version"]["digest"], "abc123")
        self.assertEqual(row["raw_output_count"], 2)
        self.assertEqual(row["generation_failure_count"], 1)
        self.assertEqual(row["strict_answer_accuracy"], 0.5)
        self.assertEqual(row["normalized_answer_accuracy"], 1.0)
        self.assertEqual(raw_archive["record_count"], 2)
        self.assertEqual(raw_archive["records"][1]["raw_response"], "not json")

    def test_rejects_a_trace_without_raw_output_field(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            config, models = self.make_fixture(root)
            trace_path = root / "experiment" / "seed_10" / "traces.jsonl"
            records = [json.loads(line) for line in trace_path.read_text().splitlines()]
            del records[0]["raw_response"]
            trace_path.write_text(
                "".join(json.dumps(record) + "\n" for record in records),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "Raw response missing"):
                build_evidence(root, [config], models)

    def test_rejects_generation_failure_count_mismatch(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            config, models = self.make_fixture(root)
            aggregate_path = root / "experiment" / "aggregate_report.json"
            aggregate = json.loads(aggregate_path.read_text(encoding="utf-8"))
            aggregate["trial_summaries"][0]["failure_count"] = 0
            aggregate_path.write_text(json.dumps(aggregate), encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "failure mismatch"):
                build_evidence(root, [config], models)


if __name__ == "__main__":
    unittest.main()
