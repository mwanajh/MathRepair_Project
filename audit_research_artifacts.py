"""Check that thesis-facing reports agree on protocol and headline metrics."""

import argparse
import json
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parent


def load_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def audit(project_dir: Path = PROJECT_DIR) -> dict[str, object]:
    primary = load_json(
        project_dir / "expanded_heldout_model_problems_repeated_experiments" / "aggregate_report.json"
    )
    profile_dir = project_dir / "expanded_heldout_model_problems_repeated_experiments_qwen2-math_7b_prompt_json"
    profile = load_json(profile_dir / "aggregate_report.json")
    sensitivity = load_json(profile_dir / "parser_sensitivity_report.json")
    category = load_json(profile_dir / "category_report.json")
    primary_7b = load_json(
        project_dir / "expanded_heldout_model_problems_repeated_experiments_qwen2-math_7b" / "aggregate_report.json"
    )
    profile_comparison = load_json(profile_dir / "model_comparison.json")
    chapter = (project_dir / "THESIS_RESULTS_CHAPTER.md").read_text(encoding="utf-8")

    checks = {
        "primary_protocol": (
            primary["model"] == "qwen2-math:1.5b"
            and primary["trial_count"] == 3
            and primary["runs_per_trial"] == 36
        ),
        "primary_local_accuracy": (
            primary["strategy_metrics"]["verified_local_repair"]["answer_accuracy"]["mean"]
            == 1.0
        ),
        "profile_protocol": (
            profile["model"] == "qwen2-math:7b"
            and profile["prompt_profile"] == "qwen2_math_json"
            and profile["trial_count"] == 3
            and profile["runs_per_trial"] == 36
        ),
        "profile_failures": sensitivity["strict_failure_count"] == 10,
        "profile_normalized_accuracy": abs(
            sensitivity["mean_normalized_answer_accuracy"] - 0.7962962962962963
        ) < 1e-12,
        "category_denominator": (
            sum(item["runs_per_trial"] for item in category["categories"].values()) == 36
        ),
        "primary_7b_failure_count": primary_7b["trial_count"] == 3,
        "comparison_candidate": profile_comparison["candidate_model"] == "qwen2-math:7b",
        "chapter_contains_headlines": all(
            phrase in chapter
            for phrase in ("90.7%", "100.0%", "13.0%", "75.0%", "85.2%", "79.6%")
        ),
    }
    return {
        "audit": "research_artifacts",
        "checks": checks,
        "all_checks_pass": all(checks.values()),
        "sources": [
            "expanded_heldout_model_problems_repeated_experiments/aggregate_report.json",
            "expanded_heldout_model_problems_repeated_experiments_qwen2-math_7b_prompt_json/aggregate_report.json",
            "expanded_heldout_model_problems_repeated_experiments_qwen2-math_7b_prompt_json/parser_sensitivity_report.json",
            "expanded_heldout_model_problems_repeated_experiments_qwen2-math_7b_prompt_json/category_report.json",
            "THESIS_RESULTS_CHAPTER.md",
        ],
    }


def render_markdown(report: dict[str, object]) -> str:
    lines = [
        "# Research Artifact Audit",
        "",
        f"All checks pass: **{report['all_checks_pass']}**",
        "",
        "| Check | Status |",
        "|---|---|",
    ]
    for name, passed in report["checks"].items():
        lines.append(f"| {name} | {'PASS' if passed else 'FAIL'} |")
    lines.extend(["", "Sources:", ""])
    lines.extend(f"- `{source}`" for source in report["sources"])
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-dir", type=Path, default=PROJECT_DIR)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--markdown", type=Path)
    args = parser.parse_args()
    report = audit(args.project_dir)
    output = args.output or args.project_dir / "research_artifact_audit.json"
    markdown = args.markdown or args.project_dir / "research_artifact_audit.md"
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    markdown.write_text(render_markdown(report), encoding="utf-8")
    print(f"All checks pass: {report['all_checks_pass']}")
    print(f"JSON: {output}")
    print(f"Markdown: {markdown}")
    if not report["all_checks_pass"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
