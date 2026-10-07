import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from error_taxonomy import ERROR_TYPE_CODES, VALID_NO_REPAIR
from natural_error_dataset import (
    LABEL_REVIEWED,
    LABEL_UNREVIEWED,
    annotation_record,
    apply_rescored_answers,
    apply_reviews,
    build_annotation_queue,
    dataset_statistics,
    equation_checkpoint_record,
    load_checkpoint_supplements,
    load_supplemental_equation_traces,
    validate_example,
    write_dataset,
)


def completed_record(benchmark_id: str, *, correct: bool) -> dict[str, object]:
    return {
        "benchmark_id": benchmark_id,
        "status": "completed",
        "model": "qwen2.5:3b",
        "subject": "algebra",
        "level": 4,
        "problem": "Solve x + 1 = 2.",
        "initial_steps": ["x = 1"],
        "final_answer_correct": correct,
        "reference_answer": "1",
        "reasoning_graph": [
            {
                "node_id": "n1",
                "state": "Solve x + 1 = 2.",
                "depends_on": [],
                "subgoal": "problem",
                "assumptions": [],
            },
            {
                "node_id": "n2",
                "state": "x = 1",
                "depends_on": ["n1"],
                "subgoal": "advance solution",
                "assumptions": [],
            },
        ],
    }


class NaturalErrorDatasetTests(unittest.TestCase):
    def test_queue_drops_reference_answers_and_leaves_labels_empty(self):
        records = {
            "b": completed_record("b", correct=False),
            "a": completed_record("a", correct=True),
            "c": {"benchmark_id": "c", "status": "failed"},
        }

        queue = build_annotation_queue(records)
        statistics = dataset_statistics(records, queue)

        self.assertEqual([item["benchmark_id"] for item in queue], ["a", "b"])
        self.assertNotIn("reference_answer", queue[0])
        self.assertEqual(queue[0]["label_status"], LABEL_UNREVIEWED)
        self.assertIsNone(queue[0]["error_type"])
        self.assertIsNone(queue[0]["recovery_action"])
        self.assertTrue(queue[0]["sampling_answer_correct"])
        self.assertFalse(queue[1]["sampling_answer_correct"])
        self.assertEqual(statistics["output_failures"], 1)
        self.assertEqual(statistics["unreviewed_count"], 2)
        self.assertFalse(statistics["trainable"])

    def test_one_reviewed_class_is_not_enough_to_train(self):
        queue = build_annotation_queue(
            {f"p{index}": completed_record(f"p{index}", correct=True) for index in range(2)}
        )
        reviewed = apply_reviews(
            queue,
            [
                {
                    "benchmark_id": "p0",
                    "trace_validity": "valid",
                    "error_location": None,
                    "error_type": VALID_NO_REPAIR,
                    "recovery_action": "CONTINUE",
                }
            ],
        )

        self.assertFalse(dataset_statistics({}, reviewed)["trainable"])

    def test_reviewed_valid_trace_uses_no_repair_class(self):
        example = annotation_record(completed_record("a", correct=True))
        example.update(
            {
                "label_status": LABEL_REVIEWED,
                "trace_validity": "valid",
                "error_location": None,
                "error_type": VALID_NO_REPAIR,
                "recovery_action": "CONTINUE",
            }
        )

        validate_example(example)

    def test_reviewed_invalid_trace_requires_location_type_and_action(self):
        example = annotation_record(completed_record("a", correct=False))
        example.update(
            {
                "label_status": LABEL_REVIEWED,
                "trace_validity": "invalid",
                "error_location": "n2",
                "error_type": "arithmetic_error",
                "recovery_action": "TOOL_EXECUTE",
            }
        )

        validate_example(example)
        example["recovery_action"] = "CONTINUE"
        with self.assertRaises(ValueError):
            validate_example(example)

    def test_valid_label_cannot_name_an_error_location(self):
        example = annotation_record(completed_record("a", correct=True))
        example.update(
            {
                "label_status": LABEL_REVIEWED,
                "trace_validity": "valid",
                "error_location": "n2",
                "error_type": VALID_NO_REPAIR,
                "recovery_action": "CONTINUE",
            }
        )

        with self.assertRaises(ValueError):
            validate_example(example)

    def test_rescored_report_updates_sampling_flag_only(self):
        record = completed_record("a", correct=False)
        updated = apply_rescored_answers(
            {"a": record},
            {"results": [{"benchmark_id": "a", "final_answer_correct": True}]},
        )

        example = annotation_record(updated["a"])

        self.assertTrue(example["sampling_answer_correct"])
        self.assertIsNone(example["trace_validity"])
        self.assertEqual(record["final_answer_correct"], False)

    def test_apply_reviews_rejects_a_location_outside_the_trace(self):
        queue = build_annotation_queue({"a": completed_record("a", correct=False)})

        with self.assertRaises(ValueError):
            apply_reviews(
                queue,
                [
                    {
                        "benchmark_id": "a",
                        "trace_validity": "invalid",
                        "error_location": "n9",
                        "error_type": "arithmetic_error",
                        "recovery_action": "TOOL_EXECUTE",
                    }
                ],
            )

    def test_write_dataset_round_trip(self):
        queue = build_annotation_queue({"a": completed_record("a", correct=True)})
        statistics = dataset_statistics(
            {"a": completed_record("a", correct=True)}, queue
        )
        with TemporaryDirectory() as directory:
            root = Path(directory)
            output = root / "queue.json"
            stats = root / "stats.json"
            write_dataset(queue, statistics, output, stats)
            loaded = json.loads(output.read_text(encoding="utf-8"))

        self.assertEqual(loaded[0]["example_id"], "math500-a")
        self.assertEqual(statistics["completed_traces"], 1)

    def test_training_requires_every_error_type(self):
        queue = []
        for code in (VALID_NO_REPAIR, *ERROR_TYPE_CODES):
            for _ in range(3):
                queue.append(
                    {
                        "label_status": LABEL_REVIEWED,
                        "error_type": code,
                        "trace_validity": "valid" if code == VALID_NO_REPAIR else "invalid",
                        "recovery_action": "CONTINUE" if code == VALID_NO_REPAIR else "BACKTRACK",
                        "sampling_answer_correct": False,
                    }
                )

        self.assertTrue(dataset_statistics({}, queue)["trainable"])
        self.assertFalse(dataset_statistics({}, queue[:-1])["trainable"])

    def test_stress_sign_trace_drops_the_reference_answer(self):
        record = load_supplemental_equation_traces()["stress-multisample/13"]
        example = annotation_record(record)

        self.assertNotIn("correct_answer", record)
        self.assertNotIn("reference_answer", example)
        self.assertTrue(example["sampling_answer_correct"])
        self.assertIn("1 - x", str(example["trace"][3]["state"]))
        reviewed = apply_reviews(
            build_annotation_queue({"stress-multisample/13": record}),
            [
                {
                    "benchmark_id": "stress-multisample/13",
                    "trace_validity": "invalid",
                    "error_location": "n4",
                    "error_type": "sign_error",
                    "recovery_action": "BACKTRACK",
                }
            ],
        )

        self.assertEqual(reviewed[0]["error_type"], "sign_error")
        self.assertEqual(reviewed[0]["error_location"], "n4")

    def test_equation_record_does_not_keep_the_reference_answer(self):
        record = equation_checkpoint_record(
            {
                "status": "completed",
                "model": "qwen2-math:1.5b",
                "problem": "x + 1 = 2",
                "steps": ["x = 1"],
                "correct_answer": "x = 1",
            },
            benchmark_id="eq/1",
            subject="algebra",
        )

        self.assertNotIn("correct_answer", record)
        self.assertTrue(record["final_answer_correct"])

    def test_stability_supplements_keep_the_first_readable_error(self):
        records = load_checkpoint_supplements()
        inequality = annotation_record(records["stability-stable/test/algebra/101.json"])
        domain = annotation_record(records["stability-stable/test/algebra/1031.json"])
        bound = annotation_record(records["stability-stable/test/algebra/1078.json"])

        self.assertNotIn("reference_answer", inequality)
        self.assertIn("extless", str(inequality["trace"][1]["state"]))
        self.assertIn("non-negative", str(domain["trace"][3]["state"]))
        self.assertIn("eq 0", str(domain["trace"][3]["state"]))
        self.assertTrue(domain["sampling_answer_correct"])
        self.assertIn("ext{sqrt}(21) + 2", str(bound["trace"][4]["state"]))
        reviewed = apply_reviews(
            build_annotation_queue(records),
            [
                {
                    "benchmark_id": "stability-stable/test/algebra/101.json",
                    "trace_validity": "invalid",
                    "error_location": "n2",
                    "error_type": "semantic_interpretation_error",
                    "recovery_action": "REPLAN",
                },
                {
                    "benchmark_id": "stability-stable/test/algebra/1078.json",
                    "trace_validity": "invalid",
                    "error_location": "n5",
                    "error_type": "sign_error",
                    "recovery_action": "BACKTRACK",
                },
            ],
        )
        by_id = {item["benchmark_id"]: item for item in reviewed}

        self.assertEqual(by_id["stability-stable/test/algebra/101.json"]["error_type"], "semantic_interpretation_error")
        self.assertEqual(by_id["stability-stable/test/algebra/1078.json"]["error_location"], "n5")

    def test_pair_trace_reuses_the_first_equation_result(self):
        record = load_checkpoint_supplements()["pair-equations/3n"]
        example = annotation_record(record)

        self.assertNotIn("reference_answer", example)
        self.assertFalse(example["sampling_answer_correct"])
        self.assertIn("both equations", str(example["trace"][4]["state"]).lower())
        reviewed = apply_reviews(
            build_annotation_queue({"pair-equations/3n": record}),
            [
                {
                    "benchmark_id": "pair-equations/3n",
                    "trace_validity": "invalid",
                    "error_location": "n5",
                    "error_type": "dependency_error",
                    "recovery_action": "BACKTRACK",
                }
            ],
        )

        self.assertEqual(reviewed[0]["error_type"], "dependency_error")

    def test_second_pair_trace_substitutes_the_wrong_equation(self):
        record = load_checkpoint_supplements()["pair-equations/6a"]
        example = annotation_record(record)

        self.assertIn(
            "Substitute the value of a from the first equation",
            str(example["trace"][3]["state"]),
        )
        reviewed = apply_reviews(
            build_annotation_queue({"pair-equations/6a": record}),
            [
                {
                    "benchmark_id": "pair-equations/6a",
                    "trace_validity": "invalid",
                    "error_location": "n4",
                    "error_type": "dependency_error",
                    "recovery_action": "BACKTRACK",
                }
            ],
        )

        self.assertEqual(reviewed[0]["error_location"], "n4")

    def test_shared_value_step_is_a_missing_assumption(self):
        record = load_checkpoint_supplements()["pair-equations/6u"]
        example = annotation_record(record)

        self.assertIn("same value of u", str(example["trace"][3]["state"]))
        reviewed = apply_reviews(
            build_annotation_queue({"pair-equations/6u": record}),
            [
                {
                    "benchmark_id": "pair-equations/6u",
                    "trace_validity": "invalid",
                    "error_location": "n4",
                    "error_type": "missing_assumption",
                    "recovery_action": "BACKTRACK",
                }
            ],
        )

        self.assertEqual(reviewed[0]["error_type"], "missing_assumption")

    def test_third_pair_trace_substitutes_the_first_value(self):
        record = load_checkpoint_supplements()["pair-equations/8d"]
        example = annotation_record(record)

        self.assertIn("Substitute d = 3", str(example["trace"][3]["state"]))
        reviewed = apply_reviews(
            build_annotation_queue({"pair-equations/8d": record}),
            [
                {
                    "benchmark_id": "pair-equations/8d",
                    "trace_validity": "invalid",
                    "error_location": "n4",
                    "error_type": "dependency_error",
                    "recovery_action": "BACKTRACK",
                }
            ],
        )

        self.assertEqual(reviewed[0]["error_type"], "dependency_error")

    def test_moved_term_keeps_the_wrong_sign(self):
        record = load_checkpoint_supplements()["sign-equation/nested-8"]
        example = annotation_record(record)

        self.assertEqual(example["trace"][11]["state"], "-x = 0")
        self.assertEqual(example["trace"][10]["state"], "-x - 1 = 1 - 1")
        reviewed = apply_reviews(
            build_annotation_queue({"sign-equation/nested-8": record}),
            [
                {
                    "benchmark_id": "sign-equation/nested-8",
                    "trace_validity": "invalid",
                    "error_location": "n12",
                    "error_type": "sign_error",
                    "recovery_action": "BACKTRACK",
                }
            ],
        )

        self.assertEqual(reviewed[0]["error_type"], "sign_error")


if __name__ == "__main__":
    unittest.main()
