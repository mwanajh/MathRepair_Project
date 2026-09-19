import unittest

from generate_dataset import generate_examples
from mathrepair_demo import verify_user_step
from repair_policy import choose_repair_action


class GenerateDatasetTests(unittest.TestCase):
    def test_generates_balanced_unique_examples(self):
        examples = generate_examples(count_per_type=3, seed=42)
        pairs = {(item["original"], item["proposed"]) for item in examples}

        self.assertEqual(len(examples), 12)
        self.assertEqual(len(pairs), 12)
        self.assertEqual(
            sum(item["has_error"] == "false" for item in examples),
            3,
        )

    def test_generated_labels_match_the_verifier(self):
        for example in generate_examples(count_per_type=3, seed=7):
            ok, error_type, repair, answer = verify_user_step(
                example["original"], example["proposed"]
            )

            self.assertEqual(str(not ok).lower(), example["has_error"])
            self.assertEqual(error_type, example["error_type"])
            self.assertEqual(repair, example["expected_repair"])
            self.assertEqual(answer, example["expected_answer"])
            self.assertEqual(
                choose_repair_action(error_type).value,
                example["expected_action"],
            )

    def test_same_seed_is_reproducible(self):
        first = generate_examples(count_per_type=2, seed=123)
        second = generate_examples(count_per_type=2, seed=123)

        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
