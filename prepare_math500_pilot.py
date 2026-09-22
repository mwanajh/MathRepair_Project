"""Create a small, stratified MATH-500 level 4-5 pilot subset."""

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Callable
from urllib import parse as url_parse
from urllib import request as url_request


DATASET_NAME = "HuggingFaceH4/MATH-500"
SOURCE_URL = "https://huggingface.co/datasets/HuggingFaceH4/MATH-500"
ROWS_ENDPOINT = "https://datasets-server.huggingface.co/rows"
PAGE_SIZE = 100
DEFAULT_OUTPUT = Path(__file__).with_name("math500_pilot_40.json")
DEFAULT_MANIFEST = Path(__file__).with_name("math500_pilot_40_manifest.json")
SUBJECT_QUOTAS = {
    "Algebra": 6,
    "Intermediate Algebra": 6,
    "Number Theory": 6,
    "Geometry": 6,
    "Counting & Probability": 6,
    "Prealgebra": 5,
    "Precalculus": 5,
}


def fetch_rows(
    fetch_page: Callable[[int, int], dict[str, object]] | None = None,
) -> list[dict[str, object]]:
    """Fetch all MATH-500 rows through the public dataset-server API."""
    if fetch_page is None:
        def fetch_page(offset: int, length: int) -> dict[str, object]:
            query = url_parse.urlencode(
                {
                    "dataset": DATASET_NAME,
                    "config": "default",
                    "split": "test",
                    "offset": offset,
                    "length": length,
                }
            )
            with url_request.urlopen(
                f"{ROWS_ENDPOINT}?{query}", timeout=60
            ) as response:
                return json.loads(response.read().decode("utf-8"))

    first_page = fetch_page(0, PAGE_SIZE)
    total = int(first_page.get("num_rows_total", 0))
    if total < 1:
        raise ValueError("MATH-500 API returned no rows.")

    pages = [first_page]
    for offset in range(PAGE_SIZE, total, PAGE_SIZE):
        pages.append(fetch_page(offset, PAGE_SIZE))

    rows: list[dict[str, object]] = []
    for page in pages:
        for item in page.get("rows", []):
            row = item.get("row") if isinstance(item, dict) else None
            if isinstance(row, dict):
                rows.append(row)
    if len(rows) != total:
        raise ValueError(f"Expected {total} rows, received {len(rows)}.")
    return rows


def select_pilot(
    rows: list[dict[str, object]],
    quotas: dict[str, int] | None = None,
) -> list[dict[str, object]]:
    """Select deterministic level 4-5 records without copying solutions."""
    subject_quotas = quotas or SUBJECT_QUOTAS
    grouped: dict[str, list[dict[str, object]]] = {
        subject: [] for subject in subject_quotas
    }
    for row in rows:
        subject = row.get("subject")
        level = row.get("level")
        if subject in grouped and isinstance(level, int) and level >= 4:
            grouped[subject].append(row)

    selected: list[dict[str, object]] = []
    for subject, quota in subject_quotas.items():
        candidates = sorted(
            grouped[subject], key=lambda row: str(row.get("unique_id", ""))
        )
        if len(candidates) < quota:
            raise ValueError(
                f"Subject {subject!r} has only {len(candidates)} level 4-5 rows; "
                f"need {quota}."
            )
        for row in candidates[:quota]:
            required = {"problem", "answer", "subject", "level", "unique_id"}
            if not required.issubset(row):
                raise ValueError(f"MATH-500 row is missing fields: {row}")
            selected.append(
                {
                    "benchmark": "MATH-500",
                    "source_dataset": DATASET_NAME,
                    "source_url": SOURCE_URL,
                    "benchmark_id": row["unique_id"],
                    "problem": row["problem"],
                    "answer": row["answer"],
                    "subject": row["subject"],
                    "level": row["level"],
                }
            )
    return selected


def write_pilot(
    output: Path,
    manifest: Path,
    records: list[dict[str, object]],
) -> None:
    """Write JSONL records and a provenance manifest."""
    output.write_text(
        json.dumps(records, indent=2, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )
    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    manifest_data = {
        "benchmark": "MATH-500",
        "source_dataset": DATASET_NAME,
        "source_url": SOURCE_URL,
        "selection_rule": "40 deterministic level 4-5 records stratified by subject",
        "subject_quotas": dict(Counter(str(record["subject"]) for record in records)),
        "problem_count": len(records),
        "level_counts": dict(Counter(int(record["level"]) for record in records)),
        "sha256": digest,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "reference_solutions_included": False,
    }
    manifest.write_text(
        json.dumps(manifest_data, indent=2, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    args = parser.parse_args()

    records = select_pilot(fetch_rows())
    write_pilot(args.output, args.manifest, records)
    print(f"Wrote {len(records)} MATH-500 pilot problems to {args.output}")
    print(f"Manifest: {args.manifest}")


if __name__ == "__main__":
    main()
