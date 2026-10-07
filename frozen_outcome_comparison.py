"""Compare global, local, and routed repair after the acceptance gate.

The natural verifier decides whether a completed trace needs repair. Policy A
then regenerates the whole solution, policy B repairs the located step, and
policy C executes the learned router's action. A candidate replaces the
original only when the symbolic gate says the new state is more reliable.
The reference answer is used after that decision, for scoring only.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import joblib

from error_category_analysis import ERROR_CATEGORIES, MINIMUM_CASES_FOR_A_STRATEGY
from error_taxonomy import VALID_NO_REPAIR
from frozen_protocol import (
    FROZEN_BASE_SEED,
    FROZEN_MAX_OUTPUT_TOKENS,
    FROZEN_MODEL,
    FROZEN_PROMPT_PROFILE,
    FROZEN_TEMPERATURE,
    FROZEN_TIMEOUT_SECONDS,
    require_generation_protocol,
)
from math500_evaluation import load_checkpoint, trace_nodes
from math_answer_scoring import answers_equivalent, extract_final_answer
from model_pipeline import OllamaMathModel
from natural_error_dataset import RECOVERY_ACTIONS
from natural_verifier import NaturalErrorVerifier
from recovery_routing import trace_text
from repair_acceptance import compare_repair_states


PROJECT_DIR = Path(__file__).resolve().parent
POLICIES = (
    "always_global_regeneration",
    "always_local_repair",
    "learned_routing",
)
POLICY_ACTION = {
    "always_global_regeneration": "GLOBAL_REGENERATE",
    "always_local_repair": "LOCAL_REPAIR",
}


def choose_action(
    policy: str,
    prediction: dict[str, object],
    routed_action: str | None,
) -> str:
    """Select one recovery action. A valid trace is not repaired."""
    if policy not in POLICIES:
        raise ValueError(f"Unknown recovery policy: {policy}")
    if not prediction.get("error_location"):
        return "CONTINUE"
    if policy == "learned_routing":
        if routed_action not in RECOVERY_ACTIONS:
            raise ValueError(f"Router returned an unknown action: {routed_action}")
        return str(routed_action)
    return POLICY_ACTION[policy]


def _located_index(nodes: list[dict[str, object]], location: object) -> int | None:
    if not location:
        return None
    for index, node in enumerate(nodes):
        if node.get("node_id") == location:
            return index
    return None


def build_candidate(
    action: str,
    problem: str,
    steps: list[str],
    nodes: list[dict[str, object]],
    prediction: dict[str, object],
    model: object,
) -> tuple[list[str], str]:
    """Generate one replacement trace without reading a reference answer."""
    if action == "CONTINUE":
        return [], "The policy kept the original trace."
    if action == "TOOL_EXECUTE":
        return [], "The symbolic tool cannot verify this text trace."
    if action == "GLOBAL_REGENERATE":
        return list(model.solve(problem)), ""
    located = _located_index(nodes, prediction.get("error_location"))
    if located is None:
        return [], "No located error was available for this repair."
    step_index = max(0, located - 1)
    if action == "REPLAN":
        prefix: list[str] = []
        bad_step = steps[0] if steps else problem
    elif action in {"LOCAL_REPAIR", "BACKTRACK"}:
        if action == "BACKTRACK":
            step_index = max(0, step_index - 1)
        prefix = steps[:step_index]
        bad_step = steps[step_index] if step_index < len(steps) else ""
    else:
        raise ValueError(f"Unknown recovery action: {action}")
    suffix = model.repair_text(
        problem,
        prefix,
        bad_step,
        str(prediction.get("error_type") or ""),
        1,
    )
    return prefix + list(suffix), ""


def apply_policy(
    *,
    policy: str,
    problem: str,
    steps: list[str],
    reference_answer: str,
    prediction: dict[str, object],
    routed_action: str | None,
    model: object,
) -> dict[str, object]:
    """Repair one trace, then let the gate decide whether it may replace."""
    action = choose_action(policy, prediction, routed_action)
    nodes = trace_nodes(problem, steps)
    initial_answer = extract_final_answer(steps, "")
    initial_correct = answers_equivalent(reference_answer, initial_answer)
    generation_note = ""
    candidate: list[str] = []
    if action != "CONTINUE":
        try:
            candidate, generation_note = build_candidate(
                action, problem, steps, nodes, prediction, model
            )
        except (ValueError, TypeError, OSError) as error:
            generation_note = str(error)
            candidate = []
    accepted = False
    rejection = generation_note
    final_steps = steps
    if candidate:
        decision = compare_repair_states(problem, steps, candidate)
        accepted = decision.accepted
        rejection = "" if decision.accepted else decision.reason
        if decision.accepted:
            final_steps = candidate
    final_answer = extract_final_answer(final_steps, "")
    candidate_answer = extract_final_answer(candidate, "") if candidate else ""
    return {
        "policy": policy,
        "action": action,
        "repair_attempted": action != "CONTINUE",
        "repair_generated": bool(candidate),
        "repair_accepted": accepted,
        "repair_rejection_reason": rejection,
        "predicted_error_location": prediction.get("error_location"),
        "predicted_error_type": str(prediction.get("error_type") or ""),
        "initial_answer": initial_answer,
        "initial_answer_correct": initial_correct,
        "candidate_answer": candidate_answer,
        "candidate_answer_correct": bool(candidate)
        and answers_equivalent(reference_answer, candidate_answer),
        "final_answer": final_answer,
        "final_answer_correct": answers_equivalent(reference_answer, final_answer),
    }


def _rate(count: int, denominator: int) -> float | None:
    if denominator == 0:
        return None
    return count / denominator


def summarize_policy(rows: list[dict[str, object]]) -> dict[str, object]:
    """Score one policy after the gate. Failures stay in the denominator."""
    completed = [row for row in rows if row.get("status") == "completed"]
    correct_before = sum(bool(row["initial_answer_correct"]) for row in completed)
    correct_after = sum(bool(row["final_answer_correct"]) for row in completed)
    accepted = [row for row in completed if row["repair_accepted"]]
    false_replacements = sum(
        bool(row["initial_answer_correct"]) and not bool(row["final_answer_correct"])
        for row in accepted
    )
    denominator = len(rows)
    return {
        "problem_count": denominator,
        "completed_count": len(completed),
        "initial_answer_correct_count": correct_before,
        "initial_answer_accuracy": _rate(correct_before, denominator),
        "final_answer_correct_count": correct_after,
        "final_answer_accuracy": _rate(correct_after, denominator),
        "repair_attempt_count": sum(bool(row["repair_attempted"]) for row in completed),
        "repair_generated_count": sum(bool(row["repair_generated"]) for row in completed),
        "repair_accepted_count": len(accepted),
        "repair_rejected_count": sum(
            bool(row["repair_attempted"]) and not bool(row["repair_accepted"])
            for row in completed
        ),
        "wrong_to_correct_count": sum(
            not bool(row["initial_answer_correct"]) and bool(row["final_answer_correct"])
            for row in completed
        ),
        "false_positive_replacement_count": false_replacements,
        "false_positive_replacement_rate": _rate(false_replacements, correct_before),
        "candidate_answer_correct_count": sum(
            bool(row["candidate_answer_correct"]) for row in completed
        ),
    }


def category_outcomes(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    """Name a strategy only when one policy wins on at least three traces."""
    completed = [row for row in rows if row.get("status") == "completed"]
    table = []
    for category in ERROR_CATEGORIES:
        matched = [
            row
            for row in completed
            if row.get("predicted_error_type") == category
            and row.get("predicted_error_location")
        ]
        observed = len({row["benchmark_id"] for row in matched})
        if observed == 0:
            status = "unobserved"
        elif observed < MINIMUM_CASES_FOR_A_STRATEGY:
            status = "sparse"
        else:
            status = "counted"
        by_policy = {}
        for policy in POLICIES:
            policy_rows = [row for row in matched if row["policy"] == policy]
            by_policy[policy] = {
                "cases": len(policy_rows),
                "accepted_repairs": sum(bool(row["repair_accepted"]) for row in policy_rows),
                "wrong_to_correct": sum(
                    not bool(row["initial_answer_correct"])
                    and bool(row["final_answer_correct"])
                    for row in policy_rows
                ),
            }
        winner = None
        if status == "counted":
            scores = {
                policy: int(item["wrong_to_correct"]) for policy, item in by_policy.items()
            }
            best = max(scores.values())
            leaders = [policy for policy, score in scores.items() if score == best and best > 0]
            if len(leaders) == 1:
                winner = leaders[0]
        table.append(
            {
                "error_category": category,
                "observed_traces": observed,
                "evidence_status": status,
                "policies": by_policy,
                "best_observed_strategy": winner,
                "label_source": "natural_verifier_prediction",
            }
        )
    return table


def run_comparison(
    problems: list[dict[str, object]],
    baselines: dict[str, dict[str, object]],
    verifier: object,
    router: object,
    model_factory,
) -> dict[str, object]:
    """Run the three policies on one frozen baseline."""
    rows: list[dict[str, object]] = []
    for index, problem_record in enumerate(problems):
        benchmark_id = str(problem_record["benchmark_id"])
        baseline = baselines.get(benchmark_id)
        problem = str(problem_record["problem"])
        reference = str(problem_record["answer"])
        shared = {
            "benchmark_id": benchmark_id,
            "subject": problem_record.get("subject", ""),
            "level": problem_record.get("level", ""),
        }
        if baseline is None or baseline.get("status") != "completed":
            for policy in POLICIES:
                rows.append(
                    {
                        **shared,
                        "policy": policy,
                        "status": "baseline_failed",
                        "repair_attempted": False,
                        "repair_generated": False,
                        "repair_accepted": False,
                        "repair_rejection_reason": "The baseline trace was not readable.",
                        "predicted_error_location": None,
                        "predicted_error_type": "",
                        "initial_answer_correct": False,
                        "candidate_answer_correct": False,
                        "final_answer_correct": False,
                    }
                )
            continue
        steps = list(baseline.get("initial_steps") or [])
        nodes = trace_nodes(problem, steps)
        prediction = verifier.predict(problem, nodes)
        routed = None
        if prediction.get("error_location"):
            routed = str(
                router.predict(
                    [trace_text({"problem": problem, "trace": nodes})]
                )[0]
            )
        model = model_factory(FROZEN_BASE_SEED + 10_000 + index)
        for policy in POLICIES:
            outcome = apply_policy(
                policy=policy,
                problem=problem,
                steps=steps,
                reference_answer=reference,
                prediction=prediction,
                routed_action=routed,
                model=model,
            )
            rows.append({**shared, "status": "completed", **outcome})
    by_policy = {
        policy: summarize_policy([row for row in rows if row["policy"] == policy])
        for policy in POLICIES
    }
    categories = category_outcomes(rows)
    return {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "experiment": "frozen_outcome_comparison",
        "model": FROZEN_MODEL,
        "prompt_profile": FROZEN_PROMPT_PROFILE,
        "max_output_tokens": FROZEN_MAX_OUTPUT_TOKENS,
        "temperature": FROZEN_TEMPERATURE,
        "base_seed": FROZEN_BASE_SEED,
        "reference_answer_usage": "scoring after the acceptance decision",
        "verifier": "natural_tfidf",
        "policies": by_policy,
        "error_categories": categories,
        "results": rows,
        "notes": [
            "Final accuracy counts an answer only after the acceptance gate.",
            "candidate_answer_correct records the generated text and is not the system result.",
            "A strategy is named only when one policy corrects more answers on at least three traces of one predicted error type.",
            "Predicted error types come from the natural verifier. They are not reviewed labels.",
            f"Valid traces use the verifier abstention {VALID_NO_REPAIR} and are not given a repair action.",
            "The earlier unguarded 10% to 2.5% result used a different output contract.",
        ],
    }


def load_natural_verifier(path: Path) -> NaturalErrorVerifier:
    """Load a verifier saved while natural_verifier.py was the main script."""
    import sys

    sys.modules["__main__"].NaturalErrorVerifier = NaturalErrorVerifier
    verifier = joblib.load(path)
    if not isinstance(verifier, NaturalErrorVerifier):
        raise ValueError("Natural verifier artifact has the wrong type.")
    return verifier


def _write_report(report: dict[str, object], path: Path) -> None:
    path.write_text(json.dumps(report, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--problems", type=Path, default=PROJECT_DIR / "math500_pilot_40.json")
    parser.add_argument(
        "--baseline-traces",
        type=Path,
        default=PROJECT_DIR / "frozen40_closed_baseline_traces.jsonl",
    )
    parser.add_argument(
        "--verifier",
        type=Path,
        default=PROJECT_DIR / "natural_verifier_tfidf.joblib",
    )
    parser.add_argument(
        "--router",
        type=Path,
        default=PROJECT_DIR / "recovery_router_tfidf.joblib",
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=PROJECT_DIR / "frozen_outcome_comparison_report.json",
    )
    parser.add_argument("--allow-larger-benchmark", action="store_true")
    args = parser.parse_args()
    problems = json.loads(args.problems.read_text(encoding="utf-8"))
    try:
        require_generation_protocol(
            problem_count=len(problems),
            model=FROZEN_MODEL,
            prompt_profile=FROZEN_PROMPT_PROFILE,
            temperature=FROZEN_TEMPERATURE,
            base_seed=FROZEN_BASE_SEED,
            max_output_tokens=FROZEN_MAX_OUTPUT_TOKENS,
            repair_attempts=0,
            allow_larger=args.allow_larger_benchmark,
        )
        baselines = load_checkpoint(args.baseline_traces)
        verifier = load_natural_verifier(args.verifier)
        router = joblib.load(args.router)

        def model_factory(seed: int) -> OllamaMathModel:
            return OllamaMathModel(
                FROZEN_MODEL,
                seed=seed,
                temperature=FROZEN_TEMPERATURE,
                timeout_seconds=FROZEN_TIMEOUT_SECONDS,
                max_output_tokens=FROZEN_MAX_OUTPUT_TOKENS,
                prompt_profile=FROZEN_PROMPT_PROFILE,
                problem_format="text",
            )

        report = run_comparison(problems, baselines, verifier, router, model_factory)
        _write_report(report, args.report)
    except (OSError, ValueError, TypeError) as error:
        parser.error(str(error))
    for policy, summary in report["policies"].items():
        accuracy = summary["final_answer_accuracy"]
        shown = "n/a" if accuracy is None else f"{accuracy:.1%}"
        print(
            f"{policy}: final={shown}, accepted={summary['repair_accepted_count']}, "
            f"false_replacements={summary['false_positive_replacement_count']}"
        )
    counted = [
        row["error_category"]
        for row in report["error_categories"]
        if row["evidence_status"] == "counted"
    ]
    print(f"Counted error categories: {', '.join(counted) if counted else 'none'}")
    print(f"Report: {args.report}")


if __name__ == "__main__":
    main()
