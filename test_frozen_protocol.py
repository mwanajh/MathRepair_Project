import json
import unittest
from pathlib import Path

from frozen_protocol import (
    FROZEN_MAX_OUTPUT_TOKENS,
    FROZEN_MODEL,
    FROZEN_PROMPT_PROFILE,
    PILOT_PROBLEM_COUNT,
    ProtocolDrift,
    choose_stability_pilot,
    prompt_profile_of,
    require_frozen_base,
    require_generation_protocol,
    scaling_block_reason,
)


PROJECT_DIR = Path(__file__).resolve().parent
PILOT_REPORTS = (
    "stability_pilot_qwen2_math_1_5b_report.json",
    "stability_pilot_qwen2_math_7b_report.json",
    "stability_pilot_qwen2_5_3b_report.json",
    "stability_pilot_qwen2_5_3b_strict_report.json",
    "stability_pilot_qwen2_5_3b_stable_report.json",
    "stability_pilot_qwen2_5_3b_closed_report.json",
)


def load_report(name: str) -> dict[str, object]:
    return json.loads((PROJECT_DIR / name).read_text(encoding="utf-8"))


class FrozenProtocolTests(unittest.TestCase):
    def test_selector_freezes_the_strict_text_protocol(self):
        reports = [load_report(name) for name in PILOT_REPORTS]
        chosen = choose_stability_pilot(reports)

        self.assertEqual(chosen["model"], FROZEN_MODEL)
        self.assertEqual(prompt_profile_of(chosen), FROZEN_PROMPT_PROFILE)
        self.assertEqual(chosen["problem_count"], PILOT_PROBLEM_COUNT)
        self.assertEqual(chosen["strict_output_contract_count"], chosen["completed_count"])
        self.assertEqual(chosen["completed_count"], PILOT_PROBLEM_COUNT)
        self.assertEqual(chosen["normalized_recovery_count"], 0)
        self.assertEqual(chosen["max_output_tokens"], FROZEN_MAX_OUTPUT_TOKENS)
        self.assertEqual(scaling_block_reason(chosen), "")
        earlier = load_report("stability_pilot_qwen2_5_3b_stable_report.json")
        self.assertIn("larger benchmark stays blocked", scaling_block_reason(earlier))

    def test_unreadable_and_forty_problem_runs_are_not_the_frozen_protocol(self):
        unreadable = load_report("stability_pilot_qwen2_math_1_5b_report.json")
        baseline = load_report("math500_full40_baseline_report.json")

        self.assertEqual(unreadable["completed_count"], 0)
        with self.assertRaises(ValueError):
            choose_stability_pilot([unreadable])
        self.assertNotEqual(baseline["problem_count"], PILOT_PROBLEM_COUNT)
        self.assertLess(
            baseline["strict_output_contract_rate"],
            load_report("stability_pilot_qwen2_5_3b_stable_report.json")[
                "strict_output_contract_rate"
            ],
        )

    def test_generation_guard_blocks_drift_and_a_larger_set(self):
        require_generation_protocol(
            problem_count=10,
            model=FROZEN_MODEL,
            prompt_profile=FROZEN_PROMPT_PROFILE,
            temperature=0.0,
            base_seed=42,
            max_output_tokens=FROZEN_MAX_OUTPUT_TOKENS,
            repair_attempts=0,
        )
        with self.assertRaises(ProtocolDrift):
            require_generation_protocol(
                problem_count=10,
                model="qwen2-math:1.5b",
                prompt_profile=FROZEN_PROMPT_PROFILE,
                temperature=0.0,
                base_seed=42,
                max_output_tokens=FROZEN_MAX_OUTPUT_TOKENS,
                repair_attempts=0,
            )
        with self.assertRaises(ProtocolDrift):
            require_generation_protocol(
                problem_count=40,
                model=FROZEN_MODEL,
                prompt_profile=FROZEN_PROMPT_PROFILE,
                temperature=0.0,
                base_seed=42,
                max_output_tokens=FROZEN_MAX_OUTPUT_TOKENS,
                repair_attempts=0,
            )

    def test_repair_guard_keeps_the_same_base_model(self):
        require_frozen_base(
            problem_count=10,
            model=FROZEN_MODEL,
            temperature=0.0,
            base_seed=42,
        )
        with self.assertRaises(ProtocolDrift):
            require_frozen_base(
                problem_count=40,
                model=FROZEN_MODEL,
                temperature=0.0,
                base_seed=42,
            )


if __name__ == "__main__":
    unittest.main()
