"""Frozen MATH-500 generation protocol.

The choice is the 10-problem stability pilot with the highest strict-output
rate. A pilot that produced no readable trace is not eligible. The closed JSON
pilot is the current freeze: all 10 traces met the strict contract. Earlier
pilots remain evidence. The 40-problem baseline is a different contract. A
larger run stays blocked while the chosen pilot still has unreadable traces,
and a run above 10 problems still needs an explicit allowance.
"""

from __future__ import annotations


PILOT_PROBLEM_COUNT = 10
FROZEN_MODEL = "qwen2.5:3b"
FROZEN_PROMPT_PROFILE = "closed_text_json"
FROZEN_PROBLEM_FORMAT = "text"
FROZEN_TEMPERATURE = 0.0
FROZEN_BASE_SEED = 42
FROZEN_MAX_OUTPUT_TOKENS = 1024
FROZEN_TIMEOUT_SECONDS = 120
FROZEN_BASELINE_REPAIR_ATTEMPTS = 0


class ProtocolDrift(ValueError):
    """A run does not match the frozen generation protocol."""


def prompt_profile_of(report: dict[str, object]) -> str:
    """Reports written before the field existed used the default text prompt."""
    profile = report.get("prompt_profile")
    return str(profile) if profile else "default"


def choose_stability_pilot(reports: list[dict[str, object]]) -> dict[str, object]:
    """Pick the readable pilot whose outputs most often met the strict contract."""
    eligible = [
        report
        for report in reports
        if int(report["problem_count"]) == PILOT_PROBLEM_COUNT
        and int(report["completed_count"]) > 0
    ]
    if not eligible:
        raise ValueError("No stability pilot produced a readable trace.")
    return max(
        eligible,
        key=lambda report: (
            float(report["strict_output_contract_rate"]),
            -int(report["normalized_recovery_count"]),
            int(report["completed_count"]),
        ),
    )


def scaling_block_reason(report: dict[str, object]) -> str:
    """Return why this pilot does not clear a larger benchmark."""
    failures = int(report["failure_count"])
    if not failures:
        return ""
    return (
        f"{failures} of {report['problem_count']} pilot traces were unreadable. "
        "The generation protocol is fixed, and a larger benchmark stays blocked."
    )


def require_generation_protocol(
    *,
    problem_count: int,
    model: str,
    prompt_profile: str,
    temperature: float,
    base_seed: int,
    max_output_tokens: int,
    repair_attempts: int,
    allow_larger: bool = False,
    allow_change: bool = False,
) -> None:
    """Reject a generation run that leaves the frozen pilot protocol."""
    expected = {
        "model": (model, FROZEN_MODEL),
        "prompt_profile": (prompt_profile, FROZEN_PROMPT_PROFILE),
        "temperature": (temperature, FROZEN_TEMPERATURE),
        "base_seed": (base_seed, FROZEN_BASE_SEED),
        "max_output_tokens": (max_output_tokens, FROZEN_MAX_OUTPUT_TOKENS),
        "repair_attempts": (repair_attempts, FROZEN_BASELINE_REPAIR_ATTEMPTS),
    }
    drift = [name for name, (actual, frozen) in expected.items() if actual != frozen]
    if drift and not allow_change:
        raise ProtocolDrift(
            "Frozen generation protocol rejects " + ", ".join(drift) + "."
        )
    if problem_count > PILOT_PROBLEM_COUNT and not allow_larger:
        raise ProtocolDrift(
            f"A run of {problem_count} problems is larger than the "
            f"{PILOT_PROBLEM_COUNT}-problem stability pilot."
        )


def require_frozen_base(
    *,
    problem_count: int,
    model: str,
    temperature: float,
    base_seed: int,
    allow_larger: bool = False,
    allow_change: bool = False,
) -> None:
    """Reject a repair run that changes the frozen base model or grows the set."""
    expected = {
        "model": (model, FROZEN_MODEL),
        "temperature": (temperature, FROZEN_TEMPERATURE),
        "base_seed": (base_seed, FROZEN_BASE_SEED),
    }
    drift = [name for name, (actual, frozen) in expected.items() if actual != frozen]
    if drift and not allow_change:
        raise ProtocolDrift("Frozen base model rejects " + ", ".join(drift) + ".")
    if problem_count > PILOT_PROBLEM_COUNT and not allow_larger:
        raise ProtocolDrift(
            f"A run of {problem_count} problems is larger than the "
            f"{PILOT_PROBLEM_COUNT}-problem stability pilot."
        )
