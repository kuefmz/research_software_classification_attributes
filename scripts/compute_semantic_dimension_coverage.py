#!/usr/bin/env python3
"""Compute semantic-dimension coverage from the final combined dataset.

The coverage values produced by this script are computed only from
``final_datasets/final_combined.jsonl``. Existing reports are read only for
validation against the earlier field-level availability table.
"""
from __future__ import annotations

import csv
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent.parent
INPUT_DATASET = ROOT / "final_datasets" / "final_combined.jsonl"
TABLES_DIR = ROOT / "results" / "tables"
OUTPUT_CSV = TABLES_DIR / "semantic_dimension_coverage.csv"
OUTPUT_TEX = TABLES_DIR / "semantic_dimension_coverage.tex"
EXISTING_AVAILABILITY_CSV = TABLES_DIR / "repository_specific_attribute_availability.csv"

PWC_SOURCE = "papers_with_code"
BIOTOOLS_SOURCE = "bio.tools"
AVAILABILITY_THRESHOLD = 5.0

DIMENSIONS = [
    {
        "semantic_dimension": "Software Identifier",
        "pwc_fields": ["item_id"],
        "biotools_fields": ["item_id"],
        "notes": "Final-dataset source-specific item identifier.",
    },
    {
        "semantic_dimension": "Software Name",
        "pwc_fields": ["software_name", "repository_title"],
        "biotools_fields": ["software_name", "repository_title"],
        "notes": "PwC does not populate software_name during alignment; repository_title is the final available name-like field.",
    },
    {
        "semantic_dimension": "Software Description",
        "pwc_fields": ["software_description", "repository_description", "somef_description"],
        "biotools_fields": ["software_description", "repository_description", "somef_description"],
        "notes": "Description is treated as populated when at least one final description field is usable.",
    },
    {
        "semantic_dimension": "Publication Metadata",
        "pwc_fields": ["paper_title", "paper_abstract", "publication_url"],
        "biotools_fields": ["paper_title", "paper_abstract", "publication_url"],
        "notes": "Publication metadata is populated when at least one publication field is usable.",
    },
    {
        "semantic_dimension": "Research Domain",
        "pwc_fields": ["labels"],
        "biotools_fields": ["labels"],
        "notes": "Uses final target labels; final_combined.jsonl is label-filtered by construction.",
    },
    {
        "semantic_dimension": "Software Functionality",
        "pwc_fields": ["tasks", "methods", "secondary_labels"],
        "biotools_fields": ["tasks", "methods", "secondary_labels"],
        "notes": "PwC methods/tasks and bio.tools EDAM operations are represented through these final schema fields.",
    },
    {
        "semantic_dimension": "Input / Output Data",
        "pwc_fields": [],
        "biotools_fields": [],
        "notes": "Not represented as a structured field in final_combined.jsonl.",
    },
    {
        "semantic_dimension": "Data Format",
        "pwc_fields": [],
        "biotools_fields": [],
        "notes": "Not represented as a structured field in final_combined.jsonl.",
    },
    {
        "semantic_dimension": "Programming Language",
        "pwc_fields": [],
        "biotools_fields": [],
        "notes": "No programming-language field is retained in final_combined.jsonl.",
    },
    {
        "semantic_dimension": "License",
        "pwc_fields": [],
        "biotools_fields": [],
        "notes": "License metadata is not retained in final_combined.jsonl.",
    },
    {
        "semantic_dimension": "Source Code Repository",
        "pwc_fields": ["repository_url"],
        "biotools_fields": ["repository_url"],
        "notes": "Uses the final source-code repository URL field retained for each record.",
    },
    {
        "semantic_dimension": "Documentation",
        "pwc_fields": ["readme_content"],
        "biotools_fields": ["readme_content"],
        "notes": "Uses README content retained in the final dataset package.",
    },
    {
        "semantic_dimension": "Benchmarks",
        "pwc_fields": [],
        "biotools_fields": [],
        "notes": "No benchmark field is retained in final_combined.jsonl.",
    },
    {
        "semantic_dimension": "Evaluation Metrics",
        "pwc_fields": [],
        "biotools_fields": [],
        "notes": "No evaluation-metric field is retained in final_combined.jsonl.",
    },
]


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            text = line.strip()
            if not text:
                continue
            try:
                records.append(json.loads(text))
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSON in {path}:{line_number}") from exc
    return records


def ensure_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple) or isinstance(value, set):
        return list(value)
    if isinstance(value, dict):
        return [value] if value else []
    if isinstance(value, str):
        text = value.strip()
        if not text or text.lower() in {"nan", "none", "null", "[]", "{}"}:
            return []
        if text.startswith("[") or text.startswith("{"):
            try:
                parsed = json.loads(text)
            except json.JSONDecodeError:
                parsed = None
            if isinstance(parsed, list):
                return parsed
            if isinstance(parsed, dict):
                return [parsed] if parsed else []
            if parsed is not None:
                return [parsed]
        if "|" in text:
            return [part.strip() for part in text.split("|") if part.strip()]
        return [text]
    return [value]


def clean_text(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, dict):
        if not value:
            return None
        for key in ("term", "name", "title", "label"):
            text = clean_text(value.get(key))
            if text:
                return text
        return None
    text = re.sub(r"\s+", " ", str(value)).strip()
    if not text or text.lower() in {"nan", "none", "null"}:
        return None
    return text


def clean_list(value: Any) -> list[str]:
    cleaned: list[str] = []
    for item in ensure_list(value):
        text = clean_text(item)
        if text and text not in cleaned:
            cleaned.append(text)
    return cleaned


def has_usable_value(value: Any) -> bool:
    if isinstance(value, list) or isinstance(value, tuple) or isinstance(value, set):
        return bool(clean_list(value))
    if isinstance(value, dict):
        return clean_text(value) is not None
    return clean_text(value) is not None


def dimension_populated(record: dict[str, Any], fields: list[str]) -> bool:
    if not fields:
        return False
    return any(has_usable_value(record.get(field)) for field in fields)


def coverage_percent(populated: int, total: int) -> float:
    return populated / total * 100 if total else 0.0


def classify(pwc_coverage: float, biotools_coverage: float, represented: bool) -> str:
    if not represented:
        return "Not represented"
    pwc_available = pwc_coverage >= AVAILABILITY_THRESHOLD
    biotools_available = biotools_coverage >= AVAILABILITY_THRESHOLD
    if pwc_available and biotools_available:
        return "Shared"
    if pwc_available:
        return "PwC-specific"
    if biotools_available:
        return "bio.tools-specific"
    return "Below threshold in both"


def compute(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_source: dict[str, list[dict[str, Any]]] = {
        PWC_SOURCE: [record for record in records if record.get("source") == PWC_SOURCE],
        BIOTOOLS_SOURCE: [record for record in records if record.get("source") == BIOTOOLS_SOURCE],
    }
    rows: list[dict[str, Any]] = []
    for dimension in DIMENSIONS:
        pwc_fields = dimension["pwc_fields"]
        biotools_fields = dimension["biotools_fields"]
        pwc_populated = sum(dimension_populated(record, pwc_fields) for record in by_source[PWC_SOURCE])
        biotools_populated = sum(dimension_populated(record, biotools_fields) for record in by_source[BIOTOOLS_SOURCE])
        pwc_total = len(by_source[PWC_SOURCE])
        biotools_total = len(by_source[BIOTOOLS_SOURCE])
        pwc_cov = coverage_percent(pwc_populated, pwc_total)
        biotools_cov = coverage_percent(biotools_populated, biotools_total)
        represented = bool(pwc_fields or biotools_fields)
        rows.append(
            {
                "semantic_dimension": dimension["semantic_dimension"],
                "pwc_fields": fields_for_csv(pwc_fields),
                "biotools_fields": fields_for_csv(biotools_fields),
                "pwc_populated": pwc_populated,
                "pwc_total": pwc_total,
                "pwc_coverage": pwc_cov,
                "biotools_populated": biotools_populated,
                "biotools_total": biotools_total,
                "biotools_coverage": biotools_cov,
                "availability_classification": classify(pwc_cov, biotools_cov, represented),
                "notes": dimension["notes"],
            }
        )
    return rows


def compute_second_pass(path: Path) -> list[dict[str, Any]]:
    source_totals: Counter[str] = Counter()
    populated: dict[tuple[str, str], int] = defaultdict(int)
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            record = json.loads(line)
            source = record.get("source")
            if source not in {PWC_SOURCE, BIOTOOLS_SOURCE}:
                continue
            source_totals[source] += 1
            for dimension in DIMENSIONS:
                fields = dimension["pwc_fields"] if source == PWC_SOURCE else dimension["biotools_fields"]
                if dimension_populated(record, fields):
                    populated[(dimension["semantic_dimension"], source)] += 1

    rows: list[dict[str, Any]] = []
    for dimension in DIMENSIONS:
        name = dimension["semantic_dimension"]
        pwc_populated = populated[(name, PWC_SOURCE)]
        biotools_populated = populated[(name, BIOTOOLS_SOURCE)]
        pwc_total = source_totals[PWC_SOURCE]
        biotools_total = source_totals[BIOTOOLS_SOURCE]
        pwc_cov = coverage_percent(pwc_populated, pwc_total)
        biotools_cov = coverage_percent(biotools_populated, biotools_total)
        represented = bool(dimension["pwc_fields"] or dimension["biotools_fields"])
        rows.append(
            {
                "semantic_dimension": name,
                "pwc_populated": pwc_populated,
                "pwc_total": pwc_total,
                "pwc_coverage": pwc_cov,
                "biotools_populated": biotools_populated,
                "biotools_total": biotools_total,
                "biotools_coverage": biotools_cov,
                "availability_classification": classify(pwc_cov, biotools_cov, represented),
            }
        )
    return rows


def fields_for_csv(fields: list[str]) -> str:
    return "; ".join(fields) if fields else "Not represented"


def format_csv_value(value: Any) -> Any:
    if isinstance(value, float):
        return f"{value:.4f}"
    return value


def write_csv_rows(path: Path, rows: list[dict[str, Any]]) -> None:
    fieldnames = [
        "semantic_dimension",
        "pwc_fields",
        "biotools_fields",
        "pwc_populated",
        "pwc_total",
        "pwc_coverage",
        "biotools_populated",
        "biotools_total",
        "biotools_coverage",
        "availability_classification",
        "notes",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: format_csv_value(row[field]) for field in fieldnames})


def latex_escape(value: Any) -> str:
    text = str(value)
    replacements = {
        "\\": r"\textbackslash{}",
        "&": r"\&",
        "%": r"\%",
        "$": r"\$",
        "#": r"\#",
        "_": r"\_",
        "{": r"\{",
        "}": r"\}",
        "~": r"\textasciitilde{}",
        "^": r"\textasciicircum{}",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return text


def format_count(value: int) -> str:
    return f"{value:,}"


def format_coverage(populated: int, total: int, percent: float) -> str:
    return f"{format_count(populated)} / {format_count(total)} ({percent:.2f}\\%)"


def write_latex(path: Path, rows: list[dict[str, Any]]) -> None:
    lines = [
        r"\begin{table}[htbp]",
        r"\centering",
        r"\small",
        r"\caption{Metadata coverage by unified semantic dimension and source.}",
        r"\label{tab:semantic-dimension-coverage}",
        r"\begin{tabular}{llll}",
        r"\toprule",
        r"Semantic Dimension & PwC Coverage & bio.tools Coverage & Availability \\",
        r"\midrule",
    ]
    for row in rows:
        values = [
            latex_escape(row["semantic_dimension"]),
            format_coverage(row["pwc_populated"], row["pwc_total"], row["pwc_coverage"]),
            format_coverage(row["biotools_populated"], row["biotools_total"], row["biotools_coverage"]),
            latex_escape(row["availability_classification"]),
        ]
        lines.append(" & ".join(values) + r" \\")
    lines.extend([r"\bottomrule", r"\end{tabular}", r"\end{table}", ""])
    path.write_text("\n".join(lines), encoding="utf-8")


def validate(records: list[dict[str, Any]], rows: list[dict[str, Any]], second_pass: list[dict[str, Any]]) -> list[str]:
    messages: list[str] = []
    source_counts = Counter(record.get("source") for record in records)
    if source_counts[PWC_SOURCE] != 42669 or source_counts[BIOTOOLS_SOURCE] != 14150:
        messages.append(f"Source-count discrepancy: recomputed {dict(source_counts)}")
    else:
        messages.append("Source totals match expected values: papers_with_code=42,669; bio.tools=14,150.")

    by_second = {row["semantic_dimension"]: row for row in second_pass}
    for row in rows:
        second = by_second[row["semantic_dimension"]]
        for key in ["pwc_populated", "pwc_total", "biotools_populated", "biotools_total", "availability_classification"]:
            if row[key] != second[key]:
                raise AssertionError(f"Second-pass mismatch for {row['semantic_dimension']}:{key}")
        for source_prefix in ["pwc", "biotools"]:
            populated = int(row[f"{source_prefix}_populated"])
            total = int(row[f"{source_prefix}_total"])
            expected = coverage_percent(populated, total)
            actual = float(row[f"{source_prefix}_coverage"])
            if abs(expected - actual) > 1e-12:
                raise AssertionError(f"Coverage percentage mismatch for {row['semantic_dimension']}:{source_prefix}")
    messages.append("Independent second pass matched all populated counts, totals, percentages, and availability classes.")

    final_fields = set().union(*(record.keys() for record in records))
    missing_fields: list[str] = []
    for dimension in DIMENSIONS:
        for field in [*dimension["pwc_fields"], *dimension["biotools_fields"]]:
            if field not in final_fields:
                missing_fields.append(f"{dimension['semantic_dimension']}:{field}")
    if missing_fields:
        raise AssertionError("Mapped fields missing from final dataset: " + "; ".join(missing_fields))
    messages.append("All mapped fields exist in final_combined.jsonl.")

    field_to_dimensions: dict[str, set[str]] = defaultdict(set)
    for dimension in DIMENSIONS:
        for field in set([*dimension["pwc_fields"], *dimension["biotools_fields"]]):
            field_to_dimensions[field].add(dimension["semantic_dimension"])
    duplicated_fields = {field: names for field, names in field_to_dimensions.items() if len(names) > 1}
    if duplicated_fields:
        raise AssertionError(f"Mapped field appears in multiple dimensions: {duplicated_fields}")
    messages.append("No mapped final-dataset field is assigned to more than one represented semantic dimension.")

    existing_messages = compare_existing_availability(rows)
    messages.extend(existing_messages)
    return messages


def compare_existing_availability(rows: list[dict[str, Any]]) -> list[str]:
    if not EXISTING_AVAILABILITY_CSV.exists():
        return ["Existing repository-specific availability table was not found; comparison skipped."]
    with EXISTING_AVAILABILITY_CSV.open("r", encoding="utf-8", newline="") as handle:
        existing = {row["semantic_field"]: row for row in csv.DictReader(handle)}

    comparisons = {
        "Source Code Repository": "repository_url",
        "Documentation": "readme_content",
    }
    for dimension_name, field in comparisons.items():
        dimension = next(row for row in rows if row["semantic_dimension"] == dimension_name)
        existing_row = existing[field]
        if int(existing_row["papers_with_code_records_with_value"]) != int(dimension["pwc_populated"]):
            raise AssertionError(f"Existing availability mismatch for {dimension_name}/PwC")
        if int(existing_row["biotools_records_with_value"]) != int(dimension["biotools_populated"]):
            raise AssertionError(f"Existing availability mismatch for {dimension_name}/bio.tools")
    return [
        "One-to-one dimensions Source Code Repository and Documentation match the existing field-level availability table.",
        "Software Name, Software Description, Publication Metadata, and Software Functionality are broader unions of final fields, so their availability classes are expected to differ from individual field-level rows.",
    ]


def main() -> None:
    records = read_jsonl(INPUT_DATASET)
    rows = compute(records)
    second_pass = compute_second_pass(INPUT_DATASET)
    validation_messages = validate(records, rows, second_pass)
    write_csv_rows(OUTPUT_CSV, rows)
    write_latex(OUTPUT_TEX, rows)
    print("\n".join(validation_messages))
    print(f"Wrote {OUTPUT_CSV.relative_to(ROOT)}")
    print(f"Wrote {OUTPUT_TEX.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
