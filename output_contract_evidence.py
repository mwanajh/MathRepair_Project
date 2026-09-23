"""Archive model-output contracts and parser-sensitivity evidence."""

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Iterable

from model_pipeline import PARSER_VERSION_BY_PROFILE, PROMPT_VERSION_BY_PROFILE
from parser_sensitivity_analysis import NORMALIZED_PARSER_VERSION


PROJECT_DIR = Path(__file__).resolve().parent
DEFAULT_OUTPUT = PROJECT_DIR / "output_contract_evidence.json"
DEFAULT_MARKDOWN = PROJECT_DIR / "output_contract_evidence.md"
DEFAULT_RAW_OUTPUTS = PROJECT_DIR / "output_contract_raw_outputs.json"

PROMPT_CONTRACTS = {
    "default": {
        "version": PROMPT_VERSION_BY_PROFILE["default"],
        "request_format": "text",
        "template": (
            "Solve this equation step by step. Return only a JSON object with "
            "one field named steps. steps must be a non-empty array of strings. "
            "Every string must be a complete equation with exactly one '=' sign. "
            "Do not include prose or Markdown.\n\nProblem: {problem}"
        ),
    },
    "qwen2_math_json": {
        "version": PROMPT_VERSION_BY_PROFILE["qwen2_math_json"],
        "request_format": "json",
        "template": (
            "Solve the equation. Output exactly one JSON object with one field "
            "named steps. steps must contain only complete equation strings, in "
            "order; do not put explanations, labels, or prose inside steps. Every "
            "string must contain exactly one '=' sign. Use plain ASCII math only: "
            "/ for fractions, * for products, and ^ for powers. Do not use LaTeX, "
            "Markdown, code fences, or any text outside the JSON object.\n\n"
            "Problem: {problem}"
        ),
    },
}

PRIMARY_PARSERS = {
    "default": {
        "version": PARSER_VERSION_BY_PROFILE["default"],
        "behavior": "strict JSON first, then equation extraction fallback",
    },
    "qwen2_math_json": {
        "version": PARSER_VERSION_BY_PROFILE["qwen2_math_json"],
        "behavior": "JSON-object recovery plus equation-only step filtering",
    },
}

MODEL_ARTIFACTS = {
    "qwen2-math:1.5b": {
        "ollama_tag": "qwen2-math:1.5b",
        "digest": "a4fdda0c6cc5d11e7d865ffc124a7dbbe3daa3d8304e6677027da9baf457a032",
        "size_bytes": 934964386,
        "format": "gguf",
        "family": "qwen2",
        "parameter_size": "1.5B",
        "quantization": "Q4_0",
    },
    "qwen2.5:3b": {
        "ollama_tag": "qwen2.5:3b",
        "digest": "357c53fb659c5076de1d65ccb0b397446227b71a42be9d1603d46168015c9e4b",
        "size_bytes": 1929912432,
        "format": "gguf",
        "family": "qwen2",
        "parameter_size": "3.1B",
        "quantization": "Q4_K_M",
    },
    "qwen2-math:7b": {
        "ollama_tag": "qwen2-math:7b",
        "digest": "28cc3a337734d0db9326604d931ccce1c9379f2310b60dee03ef76440b37bb65",
        "size_bytes": 4431400514,
        "format": "gguf",
        "family": "qwen2",
        "parameter_size": "7.6B",
        "quantization": "Q4_0",
    },
}

EXPERIMENTS = (
    {
        "experiment_id": "qwen2_math_1_5b_default",
        "directory": "expanded_heldout_model_problems_repeated_experiments",
        "model": "qwen2-math:1.5b",
        "prompt_profile": "default",
    },
    {
        "experiment_id": "qwen2_5_3b_default",
        "directory": "expanded_heldout_model_problems_repeated_experiments_qwen2.5_3b",
        "model": "qwen2.5:3b",
        "prompt_profile": "default",
    },
    {
        "experiment_id": "qwen2_math_7b_default",
        "directory": "expanded_heldout_model_problems_repeated_experiments_qwen2-math_7b",
        "model": "qwen2-math:7b",
        "prompt_profile": "default",
    },
    {
        "experiment_id": "qwen2_math_7b_qwen_json",
        "directory": "expanded_heldout_model_problems_repeated_experiments_qwen2-math_7b_prompt_json",
        "model": "qwen2-math:7b",
        "prompt_profile": "qwen2_math_json",
    },
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for block in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_json_object(path: Path) -> dict[str, object]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"Expected a JSON object: {path}")
    return data


def load_jsonl(path: Path) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    for line_number, line in enumerate(
        path.read_text(encoding="utf-8").splitlines(), start=1
    ):
        if not line.strip():
            continue
        record = json.loads(line)
        if not isinstance(record, dict):
            raise ValueError(f"Expected an object at {path}:{line_number}")
        if "raw_response" not in record:
            raise ValueError(f"Raw response missing at {path}:{line_number}")
        records.append(record)
    return records


def relative_path(path: Path, root: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def build_evidence(
    root: Path = PROJECT_DIR,
    experiments: Iterable[dict[str, str]] = EXPERIMENTS,
    model_artifacts: dict[str, dict[str, object]] = MODEL_ARTIFACTS,
) -> tuple[dict[str, object], dict[str, object]]:
    """Build a versioned manifest and a portable raw-output archive."""
    evidence_rows: list[dict[str, object]] = []
    archived_outputs: list[dict[str, object]] = []

    for config in experiments:
        experiment_dir = root / config["directory"]
        aggregate_path = experiment_dir / "aggregate_report.json"
        normalized_path = experiment_dir / "parser_sensitivity_report.json"
        aggregate = load_json_object(aggregate_path)
        model = str(aggregate.get("model", ""))
        prompt_profile = str(aggregate.get("prompt_profile") or "default")
        if model != config["model"]:
            raise ValueError(f"Model mismatch in {aggregate_path}: {model}")
        if prompt_profile != config["prompt_profile"]:
            raise ValueError(
                f"Prompt-profile mismatch in {aggregate_path}: {prompt_profile}"
            )
        if model not in model_artifacts:
            raise ValueError(f"No frozen model artifact metadata for {model}.")
        if prompt_profile not in PROMPT_CONTRACTS:
            raise ValueError(f"Unknown prompt profile: {prompt_profile}")

        base_seeds = [int(seed) for seed in aggregate["base_seeds"]]
        trace_files: list[dict[str, object]] = []
        trace_records: list[tuple[int, dict[str, object]]] = []
        for base_seed in base_seeds:
            trace_path = experiment_dir / f"seed_{base_seed}" / "traces.jsonl"
            if not trace_path.exists():
                raise ValueError(f"Missing raw trace file: {trace_path}")
            records = load_jsonl(trace_path)
            trace_records.extend((base_seed, record) for record in records)
            trace_files.append(
                {
                    "path": relative_path(trace_path, root),
                    "sha256": sha256_file(trace_path),
                    "record_count": len(records),
                }
            )

        expected_runs = int(aggregate["trial_count"]) * int(
            aggregate["runs_per_trial"]
        )
        if len(trace_records) != expected_runs:
            raise ValueError(
                f"Raw trace count mismatch for {config['experiment_id']}: "
                f"expected {expected_runs}, found {len(trace_records)}"
            )
        trace_failures = sum(
            record.get("status") == "failed" for _, record in trace_records
        )
        report_failures = sum(
            int(item["failure_count"])
            for item in aggregate.get("trial_summaries", [])
        )
        if trace_failures != report_failures:
            raise ValueError(
                f"Generation-failure mismatch for {config['experiment_id']}: "
                f"trace={trace_failures}, report={report_failures}"
            )

        strict_accuracy = float(
            aggregate["strategy_metrics"]["no_repair"]["answer_accuracy"]["mean"]
        )
        if normalized_path.exists():
            normalized = load_json_object(normalized_path)
            if int(normalized["total_runs"]) != expected_runs:
                raise ValueError(f"Normalized report run count mismatch: {normalized_path}")
            if int(normalized["strict_failure_count"]) != trace_failures:
                raise ValueError(f"Normalized failure count mismatch: {normalized_path}")
            normalized_accuracy = float(
                normalized["mean_normalized_answer_accuracy"]
            )
            normalized_source = relative_path(normalized_path, root)
        elif trace_failures == 0:
            normalized_accuracy = strict_accuracy
            normalized_source = "identity_no_generation_failures"
        else:
            raise ValueError(
                f"Missing parser-sensitivity report for failed runs: {experiment_dir}"
            )

        empty_raw_count = 0
        for base_seed, record in trace_records:
            raw_response = record["raw_response"]
            if not isinstance(raw_response, str):
                raise ValueError(
                    f"Raw response is not text in {config['experiment_id']}."
                )
            empty_raw_count += int(not raw_response)
            labels = record.get("labels", {})
            if not isinstance(labels, dict):
                labels = {}
            archived_outputs.append(
                {
                    "experiment_id": config["experiment_id"],
                    "model": model,
                    "prompt_version": PROMPT_CONTRACTS[prompt_profile]["version"],
                    "parser_version": PRIMARY_PARSERS[prompt_profile]["version"],
                    "trial_base_seed": base_seed,
                    "generation_seed": int(labels.get("seed", 0)),
                    "problem": record.get("problem", ""),
                    "category": labels.get("category", ""),
                    "status": record.get("status", ""),
                    "failure": record.get("failure", ""),
                    "raw_response": raw_response,
                    "generation_metadata": record.get("generation_metadata", {}),
                }
            )

        evidence_rows.append(
            {
                "experiment_id": config["experiment_id"],
                "experiment_directory": config["directory"],
                "model_version": model_artifacts[model],
                "prompt_profile": prompt_profile,
                "prompt_version": PROMPT_CONTRACTS[prompt_profile]["version"],
                "primary_parser_version": PRIMARY_PARSERS[prompt_profile]["version"],
                "normalized_parser_version": NORMALIZED_PARSER_VERSION,
                "run_count": expected_runs,
                "raw_output_count": len(trace_records),
                "empty_raw_output_count": empty_raw_count,
                "generation_failure_count": trace_failures,
                "strict_answer_accuracy": strict_accuracy,
                "normalized_answer_accuracy": normalized_accuracy,
                "normalization_delta_percentage_points": 100
                * (normalized_accuracy - strict_accuracy),
                "normalized_accuracy_source": normalized_source,
                "trace_files": trace_files,
            }
        )

    generated_utc = datetime.now(timezone.utc).isoformat()
    raw_archive = {
        "schema_version": "mathrepair_raw_output_archive_v1",
        "record_count": len(archived_outputs),
        "records": archived_outputs,
    }
    manifest = {
        "schema_version": "mathrepair_output_contract_evidence_v1",
        "generated_utc": generated_utc,
        "source_code_commit": "36820e1324e69865ed33e3c71e329789441292d5",
        "version_note": (
            "Historical runs predate explicit version fields. Versions are "
            "reconstructed from their saved prompt_profile and the source commit."
        ),
        "prompt_contracts": PROMPT_CONTRACTS,
        "primary_parsers": PRIMARY_PARSERS,
        "normalized_parser": {
            "version": NORMALIZED_PARSER_VERSION,
            "source": "parser_sensitivity_analysis.py",
            "behavior": "offline tolerant JSON and equation normalization",
        },
        "experiments": evidence_rows,
        "interpretation": (
            "Normalized accuracy is a parser-only sensitivity result. It does not "
            "replace strict end-to-end accuracy or establish model superiority."
        ),
    }
    return manifest, raw_archive


def percent(value: object) -> str:
    return f"{100 * float(value):.1f}%"


def render_markdown(manifest: dict[str, object]) -> str:
    lines = [
        "# Output-Contract Sensitivity Evidence",
        "",
        (
            "This archive freezes the prompt, parser, model artifact, raw outputs, "
            "generation failures, and normalized accuracy for the existing model "
            "runs. No new model inference is required."
        ),
        "",
        "| Model | Prompt version | Parser version | Runs | Raw outputs | Empty raw | Failures | Strict accuracy | Normalized accuracy | Delta |",
        "|---|---|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in manifest["experiments"]:
        lines.append(
            f"| {row['model_version']['ollama_tag']} | {row['prompt_version']} | "
            f"{row['primary_parser_version']} | {row['run_count']} | "
            f"{row['raw_output_count']} | {row['empty_raw_output_count']} | "
            f"{row['generation_failure_count']} | "
            f"{percent(row['strict_answer_accuracy'])} | "
            f"{percent(row['normalized_answer_accuracy'])} | "
            f"{float(row['normalization_delta_percentage_points']):+.1f} pp |"
        )
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            str(manifest["interpretation"]),
            "",
            (
                "The default 7B run has one empty raw response; it is retained as "
                "an observed generation failure rather than silently removed."
            ),
            "",
            "The 7B rows use the same model artifact with two output contracts. This isolates prompt/parser-contract sensitivity more directly than comparing different model sizes.",
            "",
        ]
    )
    return "\n".join(lines)


def write_artifacts(
    manifest: dict[str, object],
    raw_archive: dict[str, object],
    output: Path,
    markdown: Path,
    raw_outputs: Path,
) -> None:
    raw_outputs.write_text(
        json.dumps(raw_archive, indent=2, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )
    manifest["raw_output_archive"] = {
        "path": raw_outputs.name,
        "sha256": sha256_file(raw_outputs),
        "record_count": raw_archive["record_count"],
    }
    output.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )
    markdown.write_text(render_markdown(manifest), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=PROJECT_DIR)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--markdown", type=Path, default=DEFAULT_MARKDOWN)
    parser.add_argument("--raw-outputs", type=Path, default=DEFAULT_RAW_OUTPUTS)
    args = parser.parse_args()

    manifest, raw_archive = build_evidence(args.root)
    write_artifacts(
        manifest, raw_archive, args.output, args.markdown, args.raw_outputs
    )
    print(f"Experiments: {len(manifest['experiments'])}")
    print(f"Raw outputs: {raw_archive['record_count']}")
    print(f"Manifest: {args.output}")
    print(f"Markdown: {args.markdown}")
    print(f"Raw archive: {args.raw_outputs}")


if __name__ == "__main__":
    main()
