import unittest

from error_taxonomy import (
    ERROR_TAXONOMY,
    ERROR_TYPE_CODES,
    get_error_spec,
)
from repair_policy import RepairAction, choose_repair_action


class ErrorTaxonomyTests(unittest.TestCase):
    def test_frozen_taxonomy_has_eight_reasoning_error_types(self):
        self.assertEqual(len(ERROR_TYPE_CODES), 8)
        self.assertEqual(set(ERROR_TYPE_CODES), set(ERROR_TAXONOMY))

    def test_every_type_has_supervision_contract_and_valid_primary_action(self):
        for code in ERROR_TYPE_CODES:
            spec = get_error_spec(code)
            self.assertIsNotNone(spec)
            assert spec is not None
            self.assertTrue(spec.definition)
            self.assertTrue(spec.positive_example)
            self.assertTrue(spec.negative_example)
            self.assertTrue(spec.detection)
            self.assertTrue(spec.recommended_actions)
            self.assertIn(
                choose_repair_action(code),
                {RepairAction(action) for action in spec.recommended_actions},
            )

    def test_taxonomy_policy_preserves_existing_and_new_actions(self):
        self.assertEqual(
            choose_repair_action("arithmetic_error"), RepairAction.TOOL_EXECUTE
        )
        self.assertEqual(
            choose_repair_action("missing_assumption"), RepairAction.BACKTRACK
        )
        self.assertEqual(
            choose_repair_action("incomplete_solution"), RepairAction.REPLAN
        )
        self.assertEqual(
            choose_repair_action("unknown_error"), RepairAction.LOCAL_RESAMPLE
        )


if __name__ == "__main__":
    unittest.main()
