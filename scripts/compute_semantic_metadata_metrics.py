#!/usr/bin/env python3
"""Compute semantic metadata completeness, richness, overlap, and availability.

This analysis is intentionally grounded in the root-level final dataset package.
It reads only ``final_datasets/final_combined.jsonl`` and writes publication
tables and a methodology LaTeX snippet under ``results/``.
"""
from __future__ import annotations

import csv
import json
import math
import re
import statistics
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parent.parent
INPUT_DATASET = ROOT / "final_datasets" / "final_combined.jsonl"
TABLES_DIR = ROOT / "results" / "tables"
REPORTS_DIR = ROOT / "results" / "reports"

COMPLETENESS_SUMMARY_CSV = TABLES_DIR / "semantic_completeness_summary_by_source.csv"
COMPLETENESS_SUMMARY_TEX = TABLES_DIR / "semantic_completeness_summary_by_source.tex"
COMPLETENESS_DISTRIBUTION_CSV = TABLES_DIR / "semantic_completeness_distribution_by_source.csv"
RICHNESS_SUMMARY_CSV = TABLES_DIR / "semantic_richness_summary_by_source.csv"
RICHNESS_SUMMARY_TEX = TABLES_DIR / "semantic_richness_summary_by_source.tex"
OVERLAP_SUMMARY_CSV = TABLES_DIR / "semantic_overlap_summary.csv"
OVERLAP_SUMMARY_TEX = TABLES_DIR / "semantic_overlap_summary.tex"
AVAILABILITY_CSV = TABLES_DIR / "repository_specific_attribute_availability.csv"
AVAILABILITY_TEX = TABLES_DIR / "repository_specific_attribute_availability.tex"
RECORD_METRICS_CSV = TABLES_DIR / "semantic_record_metrics.csv"
REPORT_MD = REPORTS_DIR / "semantic_metadata_metrics_report.md"
METHODOLOGY_TEX = REPORTS_DIR / "methodology_semantic_metrics.tex"

PWC_SOURCE = "papers_with_code"
BIOTOOLS_SOURCE = "bio.tools"
SOURCE_LABELS = {
    PWC_SOURCE: "Papers with Code",
    BIOTOOLS_SOURCE: "bio.tools",
}
AVAILABILITY_THRESHOLD = 5.0

# Descriptive semantic metadata fields. Target labels are measured separately
# because all records in the final package are label-filtered by construction.
COMMON_SEMANTIC_FIELDS = [
    "paper_title",
    "paper_abstract",
    "publication_url",
    "repository_url",
    "repository_title",
    "readme_content",
    "somef_description",
    "tasks",
    "secondary_labels",
]
SOURCE_SPECIFIC_SEMANTIC_FIELDS = {
    PWC_SOURCE: ["methods"],
    BIOTOOLS_SOURCE: ["software_name", "software_description"],
}
UNIFIED_SEMANTIC_FIELDS = [
    *COMMON_SEMANTIC_FIELDS,
    "repository_description",
    "repository_keywords",
    "methods",
    "software_name",
    "software_description",
]
APPLICABLE_FIELDS = {
    source: [*COMMON_SEMANTIC_FIELDS, *specific]
    for source, specific in SOURCE_SPECIFIC_SEMANTIC_FIELDS.items()
}

# Controlled/list-like semantic values used for value richness. Long text fields
# are deliberately excluded so richness is not dominated by article/README text.
VALUE_RICHNESS_FIELDS = [
    "labels",
    "tasks",
    "methods",
    "secondary_labels",
    "repository_keywords",
]


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    """Read JSONL records from ``path``."""
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
    """Coerce values used in final datasets to a list."""
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple) or isinstance(value, set):
        return list(value)
    if isinstance(value, str):
        text = value.strip()
        if not text or text.lower() in {"nan", "none", "null", "[]"}:
            return []
        if text.startswith("[") or text.startswith("{"):
            try:
                parsed = json.loads(text)
            except json.JSONDecodeError:
                parsed = None
            if isinstance(parsed, list):
                return parsed
            if parsed is not None:
                return [parsed]
        if "|" in text:
            return [part.strip() for part in text.split("|") if part.strip()]
        return [text]
    return [value]


def clean_text(value: Any) -> str | None:
    """Return normalized text or ``None`` for empty/null-like values."""
    if value is None:
        return None
    text = re.sub(r"\s+", " ", str(value)).strip()
    if not text or text.lower() in {"nan", "none", "null"}:
        return None
    return text


def clean_list(value: Any) -> list[str]:
    """Return unique non-empty strings from scalar/list/nested values."""
    cleaned: list[str] = []
    for item in ensure_list(value):
        if isinstance(item, dict):
            item = item.get("term") or item.get("name") or item.get("title") or item.get("label")
        text = clean_text(item)
        if text and text not in cleaned:
            cleaned.append(text)
    return cleaned


def has_value(record: dict[str, Any], field: str) -> bool:
    """Return whether a final-dataset field is populated."""
    value = record.get(field)
    if isinstance(value, list):
        return bool(clean_list(value))
    return clean_text(value) is not None


def semantic_values(record: dict[str, Any]) -> set[str]:
    """Return normalized controlled semantic values for richness counting."""
    values: set[str] = set()
    for field in VALUE_RICHNESS_FIELDS:
        for value in clean_list(record.get(field)):
            values.add(re.sub(r"\s+", " ", value).strip().casefold())
    return values


def summarize(values: list[float]) -> dict[str, float]:
    """Compute deterministic summary statistics for a numeric vector."""
    if not values:
        return {
            "mean": 0.0,
            "median": 0.0,
            "std": 0.0,
            "min": 0.0,
            "q1": 0.0,
            "q3": 0.0,
            "max": 0.0,
        }
    ordered = sorted(values)
    return {
        "mean": statistics.fmean(values),
        "median": statistics.median(values),
        "std": statistics.stdev(values) if len(values) > 1 else 0.0,
        "min": ordered[0],
        "q1": percentile(ordered, 25),
        "q3": percentile(ordered, 75),
        "max": ordered[-1],
    }


def percentile(sorted_values: list[float], percentile_value: float) -> float:
    """Linear-interpolated percentile for a sorted vector."""
    if not sorted_values:
        return 0.0
    if len(sorted_values) == 1:
        return sorted_values[0]
    position = (len(sorted_values) - 1) * percentile_value / 100.0
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return sorted_values[int(position)]
    weight = position - lower
    return sorted_values[lower] * (1 - weight) + sorted_values[upper] * weight


def format_float(value: float, digits: int = 4) -> str:
    """Format floating-point output consistently for CSV/LaTeX readability."""
    return f"{value:.{digits}f}"


def source_records(records: list[dict[str, Any]], source: str) -> list[dict[str, Any]]:
    return [record for record in records if record.get("source") == source]


def compute_record_metrics(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Compute record-level completeness and richness metrics."""
    rows: list[dict[str, Any]] = []
    for record in records:
        source = record.get("source")
        applicable = APPLICABLE_FIELDS.get(source)
        if applicable is None:
            raise ValueError(f"Unsupported source in final dataset: {source}")
        populated_fields = [field for field in applicable if has_value(record, field)]
        labels = clean_list(record.get("labels"))
        semantic_value_count = len(semantic_values(record))
        rows.append(
            {
                "source": source,
                "item_id": record.get("item_id"),
                "applicable_semantic_fields": len(applicable),
                "populated_semantic_fields": len(populated_fields),
                "record_completeness": len(populated_fields) / len(applicable) if applicable else 0.0,
                "labels_per_record": len(labels),
                "unique_semantic_values": semantic_value_count,
            }
        )
    return rows


def completeness_summary(record_metrics: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Summarize record completeness by source."""
    rows: list[dict[str, Any]] = []
    for source in sorted({row["source"] for row in record_metrics}):
        group = [row for row in record_metrics if row["source"] == source]
        stats = summarize([float(row["record_completeness"]) for row in group])
        rows.append(
            {
                "source": source,
                "records": len(group),
                "applicable_semantic_fields": APPLICABLE_FIELDS[source],
                "num_applicable_semantic_fields": len(APPLICABLE_FIELDS[source]),
                "mean_record_completeness": stats["mean"],
                "median_record_completeness": stats["median"],
                "std_record_completeness": stats["std"],
                "min_record_completeness": stats["min"],
                "q1_record_completeness": stats["q1"],
                "q3_record_completeness": stats["q3"],
                "max_record_completeness": stats["max"],
            }
        )
    return rows


def completeness_distribution(record_metrics: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Count exact completeness-score levels by source."""
    rows: list[dict[str, Any]] = []
    for source in sorted({row["source"] for row in record_metrics}):
        group = [row for row in record_metrics if row["source"] == source]
        counter = Counter((row["populated_semantic_fields"], row["applicable_semantic_fields"]) for row in group)
        for (populated, applicable), count in sorted(counter.items()):
            rows.append(
                {
                    "source": source,
                    "populated_semantic_fields": populated,
                    "applicable_semantic_fields": applicable,
                    "record_completeness": populated / applicable if applicable else 0.0,
                    "records": count,
                    "percent_of_source": count / len(group) * 100 if group else 0.0,
                }
            )
    return rows


def richness_summary(record_metrics: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Summarize label, field, and controlled-value richness by source."""
    rows: list[dict[str, Any]] = []
    metrics = [
        ("labels_per_record", "Labels per record"),
        ("populated_semantic_fields", "Populated semantic fields per record"),
        ("unique_semantic_values", "Unique controlled semantic values per record"),
    ]
    for source in sorted({row["source"] for row in record_metrics}):
        group = [row for row in record_metrics if row["source"] == source]
        for key, label in metrics:
            stats = summarize([float(row[key]) for row in group])
            rows.append(
                {
                    "source": source,
                    "metric": key,
                    "metric_label": label,
                    "records": len(group),
                    "mean": stats["mean"],
                    "median": stats["median"],
                    "std": stats["std"],
                    "min": stats["min"],
                    "q1": stats["q1"],
                    "q3": stats["q3"],
                    "max": stats["max"],
                }
            )
    return rows


def field_coverage(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Compute coverage for each unified semantic field and source."""
    rows: list[dict[str, Any]] = []
    for field in UNIFIED_SEMANTIC_FIELDS:
        for source in [BIOTOOLS_SOURCE, PWC_SOURCE]:
            group = source_records(records, source)
            count = sum(has_value(record, field) for record in group)
            rows.append(
                {
                    "semantic_field": field,
                    "source": source,
                    "records_with_value": count,
                    "records": len(group),
                    "coverage_percent": count / len(group) * 100 if group else 0.0,
                }
            )
    return rows


def availability_table(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Classify fields as shared, source-specific, or unavailable by coverage."""
    coverage = field_coverage(records)
    by_field: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
    for row in coverage:
        by_field[row["semantic_field"]][row["source"]] = row

    rows: list[dict[str, Any]] = []
    for field in UNIFIED_SEMANTIC_FIELDS:
        pwc = by_field[field][PWC_SOURCE]
        bio = by_field[field][BIOTOOLS_SOURCE]
        pwc_available = float(pwc["coverage_percent"]) >= AVAILABILITY_THRESHOLD
        bio_available = float(bio["coverage_percent"]) >= AVAILABILITY_THRESHOLD
        if pwc_available and bio_available:
            availability_class = "populated_in_both_sources"
        elif pwc_available:
            availability_class = "populated_only_in_papers_with_code"
        elif bio_available:
            availability_class = "populated_only_in_bio_tools"
        else:
            availability_class = "below_threshold_in_both_sources"
        rows.append(
            {
                "semantic_field": field,
                "papers_with_code_records_with_value": pwc["records_with_value"],
                "papers_with_code_records": pwc["records"],
                "papers_with_code_coverage_percent": pwc["coverage_percent"],
                "biotools_records_with_value": bio["records_with_value"],
                "biotools_records": bio["records"],
                "biotools_coverage_percent": bio["coverage_percent"],
                "availability_threshold_percent": AVAILABILITY_THRESHOLD,
                "availability_class": availability_class,
            }
        )
    return rows


def overlap_summary(records: list[dict[str, Any]], availability_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Compute literal-label, schema-dimension, and availability-set overlap."""
    pwc = source_records(records, PWC_SOURCE)
    bio = source_records(records, BIOTOOLS_SOURCE)
    pwc_labels = {label for record in pwc for label in clean_list(record.get("labels"))}
    bio_labels = {label for record in bio for label in clean_list(record.get("labels"))}
    label_intersection = sorted(pwc_labels & bio_labels)
    label_union = sorted(pwc_labels | bio_labels)

    shared_schema_fields = sorted(set(APPLICABLE_FIELDS[PWC_SOURCE]) & set(APPLICABLE_FIELDS[BIOTOOLS_SOURCE]))
    pwc_only_schema_fields = sorted(set(APPLICABLE_FIELDS[PWC_SOURCE]) - set(APPLICABLE_FIELDS[BIOTOOLS_SOURCE]))
    bio_only_schema_fields = sorted(set(APPLICABLE_FIELDS[BIOTOOLS_SOURCE]) - set(APPLICABLE_FIELDS[PWC_SOURCE]))

    pwc_available = {
        row["semantic_field"]
        for row in availability_rows
        if float(row["papers_with_code_coverage_percent"]) >= AVAILABILITY_THRESHOLD
    }
    bio_available = {
        row["semantic_field"]
        for row in availability_rows
        if float(row["biotools_coverage_percent"]) >= AVAILABILITY_THRESHOLD
    }
    availability_intersection = sorted(pwc_available & bio_available)
    availability_union = sorted(pwc_available | bio_available)

    rows = [
        {
            "overlap_level": "literal_final_label_strings",
            "papers_with_code_count": len(pwc_labels),
            "biotools_count": len(bio_labels),
            "intersection_count": len(label_intersection),
            "union_count": len(label_union),
            "jaccard": len(label_intersection) / len(label_union) if label_union else 0.0,
            "intersection_values": "; ".join(label_intersection) if label_intersection else "none",
            "limitation": "Literal string overlap only; no ontology-based PwC-to-EDAM mapping is implemented.",
        },
        {
            "overlap_level": "shared_unified_schema_dimensions",
            "papers_with_code_count": len(APPLICABLE_FIELDS[PWC_SOURCE]),
            "biotools_count": len(APPLICABLE_FIELDS[BIOTOOLS_SOURCE]),
            "intersection_count": len(shared_schema_fields),
            "union_count": len(set(APPLICABLE_FIELDS[PWC_SOURCE]) | set(APPLICABLE_FIELDS[BIOTOOLS_SOURCE])),
            "jaccard": len(shared_schema_fields) / len(set(APPLICABLE_FIELDS[PWC_SOURCE]) | set(APPLICABLE_FIELDS[BIOTOOLS_SOURCE])),
            "intersection_values": "; ".join(shared_schema_fields),
            "limitation": "Schema-level overlap is based on manually declared applicable fields.",
        },
        {
            "overlap_level": "field_availability_ge_5_percent",
            "papers_with_code_count": len(pwc_available),
            "biotools_count": len(bio_available),
            "intersection_count": len(availability_intersection),
            "union_count": len(availability_union),
            "jaccard": len(availability_intersection) / len(availability_union) if availability_union else 0.0,
            "intersection_values": "; ".join(availability_intersection) if availability_intersection else "none",
            "limitation": "Availability uses a fixed 5% coverage threshold on final_datasets/final_combined.jsonl.",
        },
    ]
    return rows


def write_csv_rows(path: Path, rows: list[dict[str, Any]], fieldnames: list[str] | None = None) -> None:
    """Write rows to CSV with deterministic field order."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if fieldnames is None:
        fieldnames = []
        for row in rows:
            for key in row:
                if key not in fieldnames:
                    fieldnames.append(key)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: csv_value(row.get(field)) for field in fieldnames})


def csv_value(value: Any) -> Any:
    if isinstance(value, list):
        return "; ".join(str(item) for item in value)
    if isinstance(value, float):
        return format_float(value)
    return value


def latex_escape(value: Any) -> str:
    """Escape text for a simple LaTeX tabular."""
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


def write_latex_table(
    path: Path,
    rows: list[dict[str, Any]],
    columns: list[tuple[str, str]],
    caption: str,
    label: str,
    alignment: str | None = None,
) -> None:
    """Write a publication-style LaTeX table."""
    if alignment is None:
        alignment = "l" * len(columns)
    lines = [
        r"\begin{table}[t]",
        r"\centering",
        r"\small",
        rf"\caption{{{latex_escape(caption)}}}",
        rf"\label{{{label}}}",
        rf"\begin{{tabular}}{{{alignment}}}",
        r"\hline",
        " & ".join(latex_escape(header) for _, header in columns) + r" \\",
        r"\hline",
    ]
    for row in rows:
        formatted = []
        for key, _ in columns:
            value = row.get(key, "")
            if isinstance(value, float):
                value = format_float(value)
            formatted.append(latex_escape(value))
        lines.append(" & ".join(formatted) + r" \\")
    lines.extend([r"\hline", r"\end{tabular}", r"\end{table}", ""])
    path.write_text("\n".join(lines), encoding="utf-8")


def markdown_table(rows: list[dict[str, Any]], columns: list[tuple[str, str]]) -> str:
    """Render a small Markdown table."""
    if not rows:
        return "No rows."
    lines = [
        "| " + " | ".join(header for _, header in columns) + " |",
        "| " + " | ".join("---" for _ in columns) + " |",
    ]
    for row in rows:
        values = []
        for key, _ in columns:
            value = row.get(key, "")
            if isinstance(value, float):
                value = format_float(value)
            elif isinstance(value, list):
                value = "; ".join(str(item) for item in value)
            values.append(str(value))
        lines.append("| " + " | ".join(values) + " |")
    return "\n".join(lines)


def compact_completeness_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "source": SOURCE_LABELS[row["source"]],
            "records": row["records"],
            "num_applicable_semantic_fields": row["num_applicable_semantic_fields"],
            "mean_record_completeness": row["mean_record_completeness"],
            "median_record_completeness": row["median_record_completeness"],
            "std_record_completeness": row["std_record_completeness"],
            "min_record_completeness": row["min_record_completeness"],
            "max_record_completeness": row["max_record_completeness"],
        }
        for row in rows
    ]


def compact_richness_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "source": SOURCE_LABELS[row["source"]],
            "metric_label": row["metric_label"],
            "mean": row["mean"],
            "median": row["median"],
            "std": row["std"],
            "min": row["min"],
            "max": row["max"],
        }
        for row in rows
    ]


def compact_overlap_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "overlap_level": row["overlap_level"],
            "papers_with_code_count": row["papers_with_code_count"],
            "biotools_count": row["biotools_count"],
            "intersection_count": row["intersection_count"],
            "union_count": row["union_count"],
            "jaccard": row["jaccard"],
        }
        for row in rows
    ]


def compact_availability_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "semantic_field": row["semantic_field"],
            "papers_with_code_coverage_percent": row["papers_with_code_coverage_percent"],
            "biotools_coverage_percent": row["biotools_coverage_percent"],
            "availability_class": row["availability_class"],
        }
        for row in rows
    ]


def write_report(
    records: list[dict[str, Any]],
    completeness_rows: list[dict[str, Any]],
    richness_rows: list[dict[str, Any]],
    overlap_rows: list[dict[str, Any]],
    availability_rows: list[dict[str, Any]],
) -> None:
    """Write a concise Markdown report documenting definitions and outputs."""
    comp = compact_completeness_rows(completeness_rows)
    rich = compact_richness_rows(richness_rows)
    overlap = compact_overlap_rows(overlap_rows)
    availability_counts = Counter(row["availability_class"] for row in availability_rows)
    report = f"""# Semantic Metadata Metrics Report

Input dataset: `{INPUT_DATASET.relative_to(ROOT)}`

Records analyzed: {len(records):,}

## Definitions

Completeness is computed per record as:

`record_completeness = populated_applicable_semantic_fields / applicable_semantic_fields`

Administrative fields and derived target fields (`source`, `item_id`, `label`, `label_count`, `is_single_label`, `is_multi_label`) are excluded. Final target labels are summarized separately as richness because all records in the final package are label-filtered by construction.

Semantic richness is summarized with three record-level metrics: number of labels, number of populated applicable semantic fields, and number of unique controlled semantic values across `labels`, `tasks`, `methods`, `secondary_labels`, and `repository_keywords`.

Semantic overlap is computed at three levels: literal final label strings, shared applicable schema dimensions, and field availability using a {AVAILABILITY_THRESHOLD:.0f}% source-level coverage threshold. Ontology-based overlap between Papers with Code labels and EDAM labels is not implemented.

## Completeness Summary

{markdown_table(comp, [
    ("source", "Source"),
    ("records", "Records"),
    ("num_applicable_semantic_fields", "Applicable fields"),
    ("mean_record_completeness", "Mean"),
    ("median_record_completeness", "Median"),
    ("std_record_completeness", "Std."),
    ("min_record_completeness", "Min"),
    ("max_record_completeness", "Max"),
])}

## Richness Summary

{markdown_table(rich, [
    ("source", "Source"),
    ("metric_label", "Metric"),
    ("mean", "Mean"),
    ("median", "Median"),
    ("std", "Std."),
    ("min", "Min"),
    ("max", "Max"),
])}

## Semantic Overlap Summary

{markdown_table(overlap, [
    ("overlap_level", "Overlap level"),
    ("papers_with_code_count", "PwC count"),
    ("biotools_count", "bio.tools count"),
    ("intersection_count", "Intersection"),
    ("union_count", "Union"),
    ("jaccard", "Jaccard"),
])}

## Attribute Availability Classes

{markdown_table([
    {"availability_class": key, "fields": value}
    for key, value in sorted(availability_counts.items())
], [("availability_class", "Availability class"), ("fields", "Fields")])}

## Output Files

- `{COMPLETENESS_SUMMARY_CSV.relative_to(ROOT)}`
- `{COMPLETENESS_DISTRIBUTION_CSV.relative_to(ROOT)}`
- `{RICHNESS_SUMMARY_CSV.relative_to(ROOT)}`
- `{OVERLAP_SUMMARY_CSV.relative_to(ROOT)}`
- `{AVAILABILITY_CSV.relative_to(ROOT)}`
- `{RECORD_METRICS_CSV.relative_to(ROOT)}`
- `{METHODOLOGY_TEX.relative_to(ROOT)}`
"""
    REPORT_MD.write_text(report, encoding="utf-8")


def write_methodology_tex() -> None:
    """Write the Methodology subsection that cites the generated tables."""
    text = rf"""\subsection{{Completeness, Richness, Semantic Overlap, and Attribute Availability}}
\label{{subsec:methodology-semantic-metrics}}

Completeness, richness, semantic overlap, and source-specific attribute availability were computed from \texttt{{final\_datasets/final\_combined.jsonl}} using \texttt{{scripts/compute\_semantic\_metadata\_metrics.py}}. Administrative fields and derived target fields (\texttt{{source}}, \texttt{{item\_id}}, \texttt{{label}}, \texttt{{label\_count}}, \texttt{{is\_single\_label}}, and \texttt{{is\_multi\_label}}) were excluded from completeness calculations. Final target labels were summarized separately as a richness measure because the final package is label-filtered by construction.

For a record \(r\) from source \(s\), let \(A_s\) denote the set of applicable descriptive semantic fields for that source, and let \(I(r,f)\) be one when field \(f\) is non-empty after the same text/list normalization used elsewhere in the pipeline and zero otherwise. Record-level completeness was computed as
\[
C_r = \frac{{\sum_{{f \in A_s}} I(r,f)}}{{|A_s|}}.
\]
The Papers with Code applicable field set contains the shared paper, publication, repository URL/title, README/SoMEF, task, and secondary-label fields plus \texttt{{methods}}. The bio.tools applicable field set contains the same shared fields plus \texttt{{software\_name}} and \texttt{{software\_description}}. Low-coverage fields such as \texttt{{repository\_description}} and \texttt{{repository\_keywords}} are retained for availability analysis but excluded from the completeness denominator. Source-level completeness summaries are reported in Table~\ref{{tab:semantic-completeness-summary}}; exact score distributions are saved in \texttt{{results/tables/semantic\_completeness\_distribution\_by\_source.csv}}.

Semantic richness was computed with three record-level quantities: the number of final labels, the number of populated applicable semantic fields, and the number of unique controlled semantic values across \texttt{{labels}}, \texttt{{tasks}}, \texttt{{methods}}, \texttt{{secondary\_labels}}, and \texttt{{repository\_keywords}}. Long free-text fields such as abstracts and README content were excluded from the unique-value richness count so that the metric reflects controlled or list-like semantic metadata rather than document length. Source-level richness summaries are reported in Table~\ref{{tab:semantic-richness-summary}}.

Semantic overlap was evaluated at three levels. Literal label overlap compares the final Papers with Code label strings with the final EDAM top-level bio.tools label strings. Schema overlap compares the source-specific applicable field sets \(A_s\). Field-availability overlap compares fields whose source-level coverage is at least \({AVAILABILITY_THRESHOLD:.0f}\%\). The resulting overlap statistics are reported in Table~\ref{{tab:semantic-overlap-summary}}. Ontology-based semantic similarity between Papers with Code labels and EDAM topics is not implemented in this repository; therefore, overlap is limited to literal labels, declared schema dimensions, and field availability.

Repository-specific attribute availability was computed with the same \({AVAILABILITY_THRESHOLD:.0f}\%\) coverage threshold. A semantic field was classified as populated in both sources, populated only in Papers with Code, populated only in bio.tools, or below threshold in both sources. The field-level classification is reported in Table~\ref{{tab:repository-specific-attribute-availability}}.
"""
    METHODOLOGY_TEX.write_text(text, encoding="utf-8")


def main() -> None:
    TABLES_DIR.mkdir(parents=True, exist_ok=True)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    records = read_jsonl(INPUT_DATASET)
    record_rows = compute_record_metrics(records)
    completeness_rows = completeness_summary(record_rows)
    distribution_rows = completeness_distribution(record_rows)
    richness_rows = richness_summary(record_rows)
    availability_rows = availability_table(records)
    overlap_rows = overlap_summary(records, availability_rows)

    write_csv_rows(RECORD_METRICS_CSV, record_rows)
    write_csv_rows(COMPLETENESS_SUMMARY_CSV, completeness_rows)
    write_csv_rows(COMPLETENESS_DISTRIBUTION_CSV, distribution_rows)
    write_csv_rows(RICHNESS_SUMMARY_CSV, richness_rows)
    write_csv_rows(OVERLAP_SUMMARY_CSV, overlap_rows)
    write_csv_rows(AVAILABILITY_CSV, availability_rows)

    write_latex_table(
        COMPLETENESS_SUMMARY_TEX,
        compact_completeness_rows(completeness_rows),
        [
            ("source", "Source"),
            ("records", "Records"),
            ("num_applicable_semantic_fields", "Fields"),
            ("mean_record_completeness", "Mean"),
            ("median_record_completeness", "Median"),
            ("std_record_completeness", "Std."),
            ("min_record_completeness", "Min"),
            ("max_record_completeness", "Max"),
        ],
        "Metadata completeness summary by source.",
        "tab:semantic-completeness-summary",
        alignment="lrrrrrrr",
    )
    write_latex_table(
        RICHNESS_SUMMARY_TEX,
        compact_richness_rows(richness_rows),
        [
            ("source", "Source"),
            ("metric_label", "Metric"),
            ("mean", "Mean"),
            ("median", "Median"),
            ("std", "Std."),
            ("min", "Min"),
            ("max", "Max"),
        ],
        "Semantic richness summary by source.",
        "tab:semantic-richness-summary",
        alignment="llrrrrr",
    )
    write_latex_table(
        OVERLAP_SUMMARY_TEX,
        compact_overlap_rows(overlap_rows),
        [
            ("overlap_level", "Overlap level"),
            ("papers_with_code_count", "PwC"),
            ("biotools_count", "bio.tools"),
            ("intersection_count", "Intersection"),
            ("union_count", "Union"),
            ("jaccard", "Jaccard"),
        ],
        "Semantic overlap summary.",
        "tab:semantic-overlap-summary",
        alignment="lrrrrr",
    )
    write_latex_table(
        AVAILABILITY_TEX,
        compact_availability_rows(availability_rows),
        [
            ("semantic_field", "Semantic field"),
            ("papers_with_code_coverage_percent", "PwC coverage"),
            ("biotools_coverage_percent", "bio.tools coverage"),
            ("availability_class", "Availability class"),
        ],
        "Repository-specific semantic attribute availability using a 5% coverage threshold.",
        "tab:repository-specific-attribute-availability",
        alignment="lrrl",
    )
    write_report(records, completeness_rows, richness_rows, overlap_rows, availability_rows)
    write_methodology_tex()
    print(f"Wrote semantic metadata metrics from {INPUT_DATASET.relative_to(ROOT)}")
    print(f"Tables: {TABLES_DIR.relative_to(ROOT)}")
    print(f"Reports: {REPORTS_DIR.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
