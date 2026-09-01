#!/usr/bin/env python3
"""Create an early enriched subset and descriptive statistics.

This script is intentionally standalone and conservative. It analyzes only the
records for which repository artifacts are currently available, because the
GitHub/SoMEF enrichment process is still incomplete. All outputs are labelled as
``early_subset`` so they are not confused with final paper results.
"""
from __future__ import annotations

import json
import logging
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

try:
    from tqdm import tqdm
except ImportError:  # pragma: no cover
    def tqdm(iterable, **_: object):
        return iterable

sys.path.append(str(Path(__file__).resolve().parent.parent))

from src import config
from src.utils.github_utils import normalize_github_url, owner_repo
from src.utils.io_utils import configure_logging, read_jsonl, write_csv, write_jsonl
from src.utils.somef_utils import repository_slug, simplify_somef_result
from src.utils.text_utils import build_text, clean_list, clean_markup_text, flatten_for_text


ANALYSIS_STAGE = "early_subset"
INPUT_DATASET_PATHS = [config.COMBINED_ALL_JSONL]
ARTIFACTS_DIR = config.REPOSITORY_ARTIFACTS_DIR
OUTPUT_DIR = config.RESULTS_DIR / "early_subset_analysis"
OUTPUT_DATA_JSONL = OUTPUT_DIR / "early_subset_enriched_records.jsonl"
OUTPUT_DATA_CSV = OUTPUT_DIR / "early_subset_enriched_records.csv"
OUTPUT_EXCEL = OUTPUT_DIR / "early_subset_dataset_statistics.xlsx"
OUTPUT_REPORT = OUTPUT_DIR / "EARLY_SUBSET_ANALYSIS_REPORT.md"
LOG_PATH = OUTPUT_DIR / "early_subset_data_analysis.log"
GENERIC_LABELS = ["General", "Other", "Miscellaneous", "Unknown"]
GENERIC_LABELS_NORMALIZED = {label.casefold() for label in GENERIC_LABELS}

IMPORTANT_FIELDS = [
    "paper_title",
    "paper_abstract",
    "software_name",
    "software_description",
    "repository_title",
    "repository_description",
    "repository_keywords",
    "readme_content",
    "somef_description",
    "labels",
    "secondary_labels",
    "tasks",
    "methods",
]
NON_TARGET_TEXT_FIELDS = [
    "paper_title",
    "paper_abstract",
    "software_name",
    "software_description",
    "repository_title",
    "repository_description",
    "repository_keywords",
    "readme_content",
    "somef_description",
]

TEXT_LENGTH_FIELDS = [
    "paper_title",
    "paper_abstract",
    "software_name",
    "software_description",
    "repository_title",
    "repository_description",
    "repository_keywords",
    "readme_content",
    "somef_description",
]

ATTRIBUTE_COMBINATIONS = {
    "abstract_only": ["paper_abstract"],
    "title_only": ["paper_title"],
    "publication_text": ["paper_title", "paper_abstract"],
    "repository_title_keywords": ["repository_title", "repository_keywords"],
    "readme_only": ["readme_content"],
    "description_only": ["software_description", "repository_description"],
    "somef_description_only": ["somef_description"],
    "abstract_readme": ["paper_abstract", "readme_content"],
    "abstract_description": ["paper_abstract", "software_description", "repository_description"],
    "abstract_repository_title_keywords": ["paper_abstract", "repository_title", "repository_keywords"],
    "abstract_readme_description": [
        "paper_abstract",
        "readme_content",
        "software_description",
        "repository_description",
    ],
    "all_publication_metadata": ["paper_title", "paper_abstract", "publication_url"],
    "all_repository_metadata": [
        "repository_title",
        "repository_description",
        "repository_keywords",
        "readme_content",
        "somef_description",
    ],
    "all_non_target_textual_metadata": NON_TARGET_TEXT_FIELDS,
}


def configure_script_logging() -> None:
    """Configure console and file logging for a reproducible analysis run."""
    configure_logging()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    root_logger = logging.getLogger()
    if not any(isinstance(handler, logging.FileHandler) and handler.baseFilename == str(LOG_PATH) for handler in root_logger.handlers):
        file_handler = logging.FileHandler(LOG_PATH, encoding="utf-8")
        file_handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
        )
        root_logger.addHandler(file_handler)


LOGGER = logging.getLogger("early_subset_data_analysis")


def artifact_dir_for_repository(repository_url: str | None) -> Path | None:
    """Return the expected artifact folder for a repository URL."""
    normalized = normalize_github_url(repository_url)
    if not normalized:
        return None
    return ARTIFACTS_DIR / repository_slug(normalized)


def repository_title_from_url(repository_url: str | None) -> str | None:
    """Use the GitHub repository name as a fallback title."""
    normalized = normalize_github_url(repository_url)
    if not normalized:
        return None
    try:
        return owner_repo(normalized)[1]
    except ValueError:
        return None


def load_records() -> list[dict[str, Any]]:
    """Load all configured base datasets."""
    records: list[dict[str, Any]] = []
    for path in INPUT_DATASET_PATHS:
        if not path.exists():
            LOGGER.warning("Missing input dataset: %s", path)
            continue
        LOGGER.info("Loading %s", path)
        records.extend(read_jsonl(path))
    LOGGER.info("Loaded %s candidate records", f"{len(records):,}")
    return records


def parse_somef_json(path: Path) -> tuple[dict[str, Any], str | None]:
    """Parse and simplify one SoMEF JSON file without crashing the analysis."""
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {}, f"json_parse_error: {exc}"
    if isinstance(raw, dict) and raw.get("error"):
        return {}, f"somef_error: {raw.get('error')}"
    try:
        simplified = simplify_somef_result(raw if isinstance(raw, dict) else {})
    except Exception as exc:
        return {}, f"somef_simplify_error: {exc}"
    return simplified, None


def enrich_record(record: dict[str, Any]) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    """Attach currently available README/SoMEF artifacts to one record."""
    repository_url = record.get("repository_url")
    normalized = normalize_github_url(repository_url)
    artifact_dir = artifact_dir_for_repository(repository_url)
    error_row: dict[str, Any] | None = None
    if not artifact_dir:
        return None, {
            "item_id": record.get("item_id"),
            "repository_url": repository_url,
            "error_type": "missing_or_invalid_repository_url",
            "enrichment_path": None,
        }

    readme_path = artifact_dir / "README.md"
    somef_path = artifact_dir / "somef.json"
    metadata_path = artifact_dir / "metadata.json"

    readme_content = readme_path.read_text(encoding="utf-8", errors="replace") if readme_path.exists() else None
    somef_summary: dict[str, Any] = {}
    somef_error = None
    if somef_path.exists():
        somef_summary, somef_error = parse_somef_json(somef_path)
    metadata: dict[str, Any] = {}
    if metadata_path.exists():
        try:
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            error_row = {
                "item_id": record.get("item_id"),
                "repository_url": repository_url,
                "error_type": f"metadata_json_parse_error: {exc}",
                "enrichment_path": str(artifact_dir),
            }

    enrichment_available = bool(readme_content or (somef_path.exists() and not somef_error))
    if not enrichment_available:
        error_row = {
            "item_id": record.get("item_id"),
            "repository_url": repository_url,
            "error_type": somef_error or "missing_readme_and_somef",
            "enrichment_path": str(artifact_dir),
        }
        return None, error_row

    enriched = dict(record)
    enriched.update(
        {
            "analysis_stage": ANALYSIS_STAGE,
            "repository_url_normalized": normalized,
            "repository_title": clean_markup_text(
                somef_summary.get("title") or metadata.get("repository_title") or repository_title_from_url(repository_url)
            ),
            "repository_description": clean_markup_text(record.get("repository_description")),
            "repository_keywords": clean_list(somef_summary.get("keywords") or record.get("repository_keywords")),
            "readme_content": readme_content,
            "somef_description": clean_markup_text(somef_summary.get("somef_description")),
            "somef_citation": clean_markup_text(somef_summary.get("citation")),
            "enrichment_available": True,
            "enrichment_path": str(artifact_dir),
            "somef_json_path": str(somef_path) if somef_path.exists() else None,
            "readme_path": str(readme_path) if readme_path.exists() else None,
        }
    )
    return enriched, error_row


def list_count(records: list[dict[str, Any]], field: str) -> Counter:
    """Count labels/tasks/methods stored as list-like fields."""
    counter: Counter = Counter()
    for record in records:
        counter.update(clean_list(record.get(field)))
    return counter


def table_from_counter(counter: Counter, name: str) -> pd.DataFrame:
    """Convert a Counter to a sorted table with percentages."""
    total = sum(counter.values())
    rows = [
        {"value": key, "support": value, "percent": (value / total * 100) if total else 0.0, "field": name}
        for key, value in counter.most_common()
    ]
    return pd.DataFrame(rows, columns=["value", "support", "percent", "field"])


def filter_top_level_labels(
    records: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], pd.DataFrame, dict[str, int]]:
    """Remove generic top-level labels and summarize the filtering step.

    The base preparation pipeline stores the labels used for modelling in the
    ``labels`` field. This analysis keeps those top-level labels and excludes
    broad catch-all classes that do not provide useful supervision.
    """
    before_counts = list_count(records, "labels")
    filtered_records: list[dict[str, Any]] = []
    removed_records = 0

    for record in records:
        original_labels = clean_list(record.get("labels"))
        filtered_labels = [
            label for label in original_labels if label.casefold() not in GENERIC_LABELS_NORMALIZED
        ]
        if not filtered_labels:
            removed_records += 1
            continue
        filtered_record = dict(record)
        filtered_record["labels"] = filtered_labels
        filtered_records.append(filtered_record)

    after_counts = list_count(filtered_records, "labels")
    labels = sorted(set(before_counts) | set(after_counts), key=lambda value: value.casefold())
    rows = []
    for label in labels:
        before = before_counts.get(label, 0)
        after = after_counts.get(label, 0)
        is_generic = label.casefold() in GENERIC_LABELS_NORMALIZED
        rows.append(
            {
                "label": label,
                "count_before_filtering": before,
                "count_after_filtering": after,
                "removed_count": before - after,
                "removed_reason": "excluded_generic_label" if is_generic else "kept",
            }
        )

    metadata = {
        "records_before_label_filtering": len(records),
        "records_after_label_filtering": len(filtered_records),
        "records_removed_by_label_filtering": removed_records,
    }
    return filtered_records, pd.DataFrame(rows), metadata


def text_length_table(records: list[dict[str, Any]]) -> pd.DataFrame:
    """Compute length statistics for text-bearing metadata attributes."""
    rows = []
    for field in TEXT_LENGTH_FIELDS:
        lengths = [len(flatten_for_text(record.get(field))) for record in records if flatten_for_text(record.get(field))]
        arr = np.array(lengths, dtype=float)
        rows.append(
            {
                "field": field,
                "non_missing": len(lengths),
                "mean_chars": float(arr.mean()) if len(arr) else 0.0,
                "std_chars": float(arr.std()) if len(arr) else 0.0,
                "median_chars": float(np.median(arr)) if len(arr) else 0.0,
                "min_chars": float(arr.min()) if len(arr) else 0.0,
                "max_chars": float(arr.max()) if len(arr) else 0.0,
            }
        )
    return pd.DataFrame(rows)


def field_coverage_table(records: list[dict[str, Any]]) -> pd.DataFrame:
    """Compute non-missing coverage for important fields."""
    total = len(records)
    rows = []
    for field in IMPORTANT_FIELDS + ["repository_url", "enrichment_available"]:
        count = sum(bool(clean_list(record.get(field)) if isinstance(record.get(field), list) else flatten_for_text(record.get(field))) for record in records)
        rows.append({"field": field, "non_missing": count, "missing": total - count, "coverage_percent": count / total * 100 if total else 0.0})
    return pd.DataFrame(rows)


def missingness_table(records: list[dict[str, Any]]) -> pd.DataFrame:
    """Compute a missingness table for fields used in early analysis."""
    return field_coverage_table(records).assign(missing_percent=lambda df: 100 - df["coverage_percent"])


def attribute_coverage_table(records: list[dict[str, Any]]) -> pd.DataFrame:
    """Count records with usable text for each attribute combination."""
    rows = []
    total = len(records)
    for name, fields in ATTRIBUTE_COMBINATIONS.items():
        count = sum(bool(build_text(record, fields)) for record in records)
        rows.append({"attribute_combination": name, "records_with_text": count, "coverage_percent": count / total * 100 if total else 0.0})
    return pd.DataFrame(rows)


def cooccurrence_table(records: list[dict[str, Any]]) -> pd.DataFrame:
    """Build a class co-occurrence matrix from multi-label records."""
    labels = sorted({label for record in records for label in clean_list(record.get("labels"))})
    matrix = pd.DataFrame(0, index=labels, columns=labels, dtype=int)
    for record in records:
        record_labels = clean_list(record.get("labels"))
        if len(record_labels) < 2:
            continue
        for left in record_labels:
            for right in record_labels:
                matrix.loc[left, right] += 1
    matrix.index.name = "label"
    return matrix.reset_index()


def summary_tables(
    records: list[dict[str, Any]],
    errors: list[dict[str, Any]],
    label_filtering_summary: pd.DataFrame,
    label_filtering_metadata: dict[str, int],
) -> dict[str, pd.DataFrame]:
    """Generate all requested statistics as DataFrames."""
    label_counts = table_from_counter(list_count(records, "labels"), "labels")
    labels_per_record = [len(clean_list(record.get("labels"))) for record in records]
    tasks_per_record = [len(clean_list(record.get("tasks"))) for record in records]
    methods_per_record = [len(clean_list(record.get("methods"))) for record in records]
    source_counter = Counter(record.get("source") for record in records)

    summary = pd.DataFrame(
        [
            {"metric": "analysis_stage", "value": ANALYSIS_STAGE},
            {"metric": "warning", "value": "This is an early subset analysis. GitHub/SoMEF enrichment is incomplete."},
            {"metric": "label_hierarchy_note", "value": "Labels are hierarchical; only top-level labels are used."},
            {"metric": "excluded_generic_labels", "value": ", ".join(GENERIC_LABELS)},
            {"metric": "records_before_label_filtering", "value": label_filtering_metadata["records_before_label_filtering"]},
            {"metric": "records_after_label_filtering", "value": label_filtering_metadata["records_after_label_filtering"]},
            {"metric": "records_removed_by_label_filtering", "value": label_filtering_metadata["records_removed_by_label_filtering"]},
            {"metric": "total_records", "value": len(records)},
            {"metric": "records_with_repository_urls", "value": sum(bool(record.get("repository_url")) for record in records)},
            {"metric": "records_with_enrichment_available", "value": sum(bool(record.get("enrichment_available")) for record in records)},
            {"metric": "records_with_readme", "value": sum(bool(record.get("readme_content")) for record in records)},
            {"metric": "records_with_repository_description", "value": sum(bool(record.get("repository_description")) for record in records)},
            {"metric": "records_with_repository_keywords", "value": sum(bool(record.get("repository_keywords")) for record in records)},
            {"metric": "records_with_somef_description", "value": sum(bool(record.get("somef_description")) for record in records)},
            {"metric": "records_with_paper_title", "value": sum(bool(record.get("paper_title")) for record in records)},
            {"metric": "records_with_paper_abstract", "value": sum(bool(record.get("paper_abstract")) for record in records)},
            {"metric": "records_with_software_name", "value": sum(bool(record.get("software_name")) for record in records)},
            {"metric": "records_with_software_description", "value": sum(bool(record.get("software_description")) for record in records)},
            {"metric": "records_with_labels", "value": sum(bool(clean_list(record.get("labels"))) for record in records)},
            {"metric": "single_label_records", "value": sum(len(clean_list(record.get("labels"))) == 1 for record in records)},
            {"metric": "multi_label_records", "value": sum(len(clean_list(record.get("labels"))) > 1 for record in records)},
            {"metric": "num_unique_labels", "value": len(label_counts)},
            {"metric": "min_label_support", "value": int(label_counts["support"].min()) if len(label_counts) else 0},
            {"metric": "max_label_support", "value": int(label_counts["support"].max()) if len(label_counts) else 0},
            {"metric": "median_label_support", "value": float(label_counts["support"].median()) if len(label_counts) else 0.0},
            {"metric": "enrichment_errors", "value": len(errors)},
        ]
    )

    count_stats = pd.DataFrame(
        [
            {"field": "labels", "mean": np.mean(labels_per_record), "median": np.median(labels_per_record), "max": np.max(labels_per_record) if labels_per_record else 0},
            {"field": "tasks", "mean": np.mean(tasks_per_record), "median": np.median(tasks_per_record), "max": np.max(tasks_per_record) if tasks_per_record else 0},
            {"field": "methods", "mean": np.mean(methods_per_record), "median": np.median(methods_per_record), "max": np.max(methods_per_record) if methods_per_record else 0},
        ]
    )

    tables = {
        "summary": summary,
        "source_counts": table_from_counter(source_counter, "source"),
        "field_coverage": field_coverage_table(records),
        "missingness": missingness_table(records),
        "label_filtering_summary": label_filtering_summary,
        "label_distribution": label_counts,
        "secondary_label_distribution": table_from_counter(list_count(records, "secondary_labels"), "secondary_labels"),
        "task_distribution": table_from_counter(list_count(records, "tasks"), "tasks"),
        "method_distribution": table_from_counter(list_count(records, "methods"), "methods"),
        "text_lengths": text_length_table(records),
        "attribute_combination_coverage": attribute_coverage_table(records),
        "class_cooccurrence": cooccurrence_table(records),
        "enrichment_errors": pd.DataFrame(errors),
        "count_statistics": count_stats,
        "top_labels": label_counts.head(25),
        "bottom_labels": label_counts.tail(25),
    }
    return tables


def write_tables(tables: dict[str, pd.DataFrame]) -> None:
    """Write statistics to CSV files and one multi-sheet Excel workbook."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for name, table in tables.items():
        table.to_csv(OUTPUT_DIR / f"{name}.csv", index=False)
    try:
        with pd.ExcelWriter(OUTPUT_EXCEL) as writer:
            for name, table in tables.items():
                table.to_excel(writer, sheet_name=name[:31], index=False)
    except Exception as exc:
        LOGGER.warning("Could not write Excel workbook %s: %s", OUTPUT_EXCEL, exc)


def dataframe_to_markdown(table: pd.DataFrame) -> str:
    """Render a simple Markdown table without optional pandas dependencies."""
    if table.empty:
        return ""
    columns = list(table.columns)
    rows = table.astype(str).values.tolist()
    header = "| " + " | ".join(columns) + " |"
    separator = "| " + " | ".join("---" for _ in columns) + " |"
    body = ["| " + " | ".join(row) + " |" for row in rows]
    return "\n".join([header, separator, *body])


def write_report(tables: dict[str, pd.DataFrame], records: list[dict[str, Any]]) -> None:
    """Write a short Markdown report for quick inspection."""
    summary = {row["metric"]: row["value"] for _, row in tables["summary"].iterrows()}
    final_label_distribution = tables["label_distribution"].copy()
    if not final_label_distribution.empty:
        final_label_distribution = final_label_distribution.rename(
            columns={"value": "label", "support": "count", "percent": "percent"}
        )[["label", "count", "percent"]]
        final_label_distribution["percent"] = final_label_distribution["percent"].map(lambda value: f"{value:.2f}")
        final_label_distribution_md = dataframe_to_markdown(final_label_distribution)
    else:
        final_label_distribution_md = "No labels remain after filtering."
    report = f"""# Early Subset Analysis Report

**This is an early subset analysis. GitHub/SoMEF enrichment is incomplete, so results should be interpreted as preliminary.**

## Overview

- Analysis stage: `{ANALYSIS_STAGE}`
- Enriched subset records: {len(records):,}
- Records with README: {summary.get("records_with_readme", 0)}
- Records with SoMEF description: {summary.get("records_with_somef_description", 0)}
- Unique labels: {summary.get("num_unique_labels", 0)}
- Single-label records: {summary.get("single_label_records", 0)}
- Multi-label records: {summary.get("multi_label_records", 0)}

## Label filtering

- Labels are hierarchical.
- Only top-level labels are used for this early subset analysis.
- Generic labels such as General/Other/Miscellaneous/Unknown were excluded.
- Records removed by label filtering: {summary.get("records_removed_by_label_filtering", 0)}
- Records after label filtering: {summary.get("records_after_label_filtering", len(records))}

Final label distribution after filtering:

{final_label_distribution_md}

## Outputs

- Enriched subset JSONL: `{OUTPUT_DATA_JSONL}`
- Enriched subset CSV: `{OUTPUT_DATA_CSV}`
- Statistics workbook: `{OUTPUT_EXCEL}`
- CSV tables: `{OUTPUT_DIR}`

## Interpretation Note

The enrichment process is still running. Coverage of README, repository metadata,
and SoMEF-derived fields reflects only the repository artifacts currently present
under `{ARTIFACTS_DIR}`.
"""
    OUTPUT_REPORT.write_text(report, encoding="utf-8")


def main() -> None:
    configure_script_logging()
    LOGGER.info("Starting early subset data analysis")
    raw_records = load_records()
    enriched_records: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    for record in tqdm(raw_records, desc="Attaching repository artifacts"):
        enriched, error = enrich_record(record)
        if enriched:
            enriched_records.append(enriched)
        if error:
            errors.append(error)
    LOGGER.info("Early enriched subset records: %s", f"{len(enriched_records):,}")
    LOGGER.info("Enrichment errors/missing rows: %s", f"{len(errors):,}")
    filtered_records, label_filtering_summary, label_filtering_metadata = filter_top_level_labels(enriched_records)
    LOGGER.info(
        "Label filtering removed %s records; %s records remain",
        f"{label_filtering_metadata['records_removed_by_label_filtering']:,}",
        f"{len(filtered_records):,}",
    )
    write_jsonl(filtered_records, OUTPUT_DATA_JSONL)
    write_csv(filtered_records, OUTPUT_DATA_CSV)
    tables = summary_tables(filtered_records, errors, label_filtering_summary, label_filtering_metadata)
    write_tables(tables)
    write_report(tables, filtered_records)
    LOGGER.info("Wrote early subset analysis outputs to %s", OUTPUT_DIR)


if __name__ == "__main__":
    main()
