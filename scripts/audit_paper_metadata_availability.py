#!/usr/bin/env python3
"""Audit row-level metadata availability for the paper's retained master cohort.

This script is deliberately read-only. It reports source-specific availability
counts and percentages for the textual metadata fields used in the manuscript,
including GitHub repository title/name and GitHub Topics.

Example
-------
python scripts/audit_paper_metadata_availability.py \
    --input /content/drive/MyDrive/phd_research_software/data/frozen/paper_v1/master.jsonl
"""
from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable


FIELDS = [
    ("paper_title", "Publication title"),
    ("paper_abstract", "Abstract"),
    ("repository_title", "GitHub repository title/name"),
    ("readme_content", "README"),
    ("somef_description", "SoMEF description"),
    ("repository_keywords", "GitHub Topics"),
]


def is_present(value: Any) -> bool:
    """Return True when a field contains a usable, non-empty value."""
    if value is None:
        return False

    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return False
        if stripped.lower() in {"none", "null", "nan", "[]", "{}"}:
            return False
        return True

    if isinstance(value, (list, tuple, set)):
        return any(is_present(item) for item in value)

    if isinstance(value, dict):
        return any(is_present(item) for item in value.values())

    return True


def iter_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(
                    f"Invalid JSON on line {line_number} of {path}: {exc}"
                ) from exc
            if not isinstance(row, dict):
                raise ValueError(
                    f"Expected an object on line {line_number} of {path}, "
                    f"got {type(row).__name__}."
                )
            yield row


def audit(path: Path) -> tuple[Counter[str], dict[str, Counter[str]]]:
    totals: Counter[str] = Counter()
    present: dict[str, Counter[str]] = defaultdict(Counter)

    for row in iter_jsonl(path):
        source = str(row.get("source", "")).strip()
        if not source:
            raise ValueError("Encountered a row without a non-empty 'source' field.")

        totals[source] += 1
        for field, _ in FIELDS:
            if is_present(row.get(field)):
                present[source][field] += 1

    if not totals:
        raise ValueError(f"No records found in {path}.")

    return totals, present


def result_rows(
    totals: Counter[str], present: dict[str, Counter[str]]
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for source in sorted(totals):
        denominator = totals[source]
        for field, label in FIELDS:
            count = present[source][field]
            rows.append(
                {
                    "source": source,
                    "field": field,
                    "label": label,
                    "records_with_value": count,
                    "records": denominator,
                    "coverage_percent": 100.0 * count / denominator,
                }
            )
    return rows


def print_report(rows: list[dict[str, Any]]) -> None:
    sources = sorted({str(row["source"]) for row in rows})

    print("\nMetadata availability by source")
    print("=" * 80)
    for source in sources:
        source_rows = [row for row in rows if row["source"] == source]
        denominator = source_rows[0]["records"]
        print(f"\n{source} (N={denominator:,})")
        for row in source_rows:
            print(
                f"  {row['label']:<30} "
                f"{row['records_with_value']:,} "
                f"({row['coverage_percent']:.2f}%)"
            )

    print("\nReady-to-copy manuscript rows")
    print("=" * 80)
    header = ["Source"] + [label for _, label in FIELDS]
    print(" | ".join(header))
    for source in sources:
        source_rows = {
            str(row["field"]): row for row in rows if row["source"] == source
        }
        cells = [source]
        for field, _ in FIELDS:
            row = source_rows[field]
            cells.append(
                f"{row['records_with_value']:,} "
                f"({row['coverage_percent']:.2f}%)"
            )
        print(" | ".join(cells))


def write_csv(rows: list[dict[str, Any]], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    columns = [
        "source",
        "field",
        "label",
        "records_with_value",
        "records",
        "coverage_percent",
    ]
    with output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Report source-specific metadata availability in the frozen paper "
            "master cohort."
        )
    )
    parser.add_argument(
        "--input",
        type=Path,
        required=True,
        help="Path to the frozen master JSONL used by the paper.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Optional CSV path for the audit results.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not args.input.exists():
        raise FileNotFoundError(f"Input file does not exist: {args.input}")

    totals, present = audit(args.input)
    rows = result_rows(totals, present)
    print_report(rows)

    if args.output is not None:
        write_csv(rows, args.output)
        print(f"\nWrote CSV: {args.output}")


if __name__ == "__main__":
    main()
