#!/usr/bin/env python3
"""Build the root-level final dataset package used by final analyses."""
from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import pandas as pd

sys.path.append(str(Path(__file__).resolve().parent.parent))

from src.utils.io_utils import read_jsonl, write_jsonl
from src.utils.text_utils import build_text, clean_list


ROOT = Path(__file__).resolve().parent.parent
SOURCE_DATASET = ROOT / "data" / "final_edam_top_level" / "combined_all_with_somef.jsonl"
OUTPUT_DIR = ROOT / "final_datasets"

SINGLE_JSONL = OUTPUT_DIR / "final_single_label.jsonl"
MULTI_ONLY_JSONL = OUTPUT_DIR / "final_multi_label_only.jsonl"
COMBINED_JSONL = OUTPUT_DIR / "final_combined.jsonl"

FINAL_FIELDS = [
    "source",
    "item_id",
    "software_name",
    "software_description",
    "paper_title",
    "paper_abstract",
    "publication_url",
    "repository_url",
    "repository_title",
    "repository_description",
    "repository_keywords",
    "readme_content",
    "somef_description",
    "tasks",
    "methods",
    "secondary_labels",
    "labels",
]

ATTRIBUTE_COMBINATIONS = {
    "abstract_only": ["paper_abstract"],
    "title_only": ["paper_title"],
    "repository_title_keywords": ["repository_title", "repository_keywords"],
    "abstract_readme_description": [
        "paper_abstract",
        "readme_content",
        "software_description",
        "repository_description",
    ],
    "abstract_repository_title_keywords": ["paper_abstract", "repository_title", "repository_keywords"],
    "all_publication_metadata": ["paper_title", "paper_abstract", "publication_url"],
    "all_repository_metadata": [
        "repository_title",
        "repository_description",
        "repository_keywords",
        "readme_content",
        "somef_description",
    ],
    "all_non_target_textual_metadata": [
        "paper_title",
        "paper_abstract",
        "software_name",
        "software_description",
        "repository_title",
        "repository_description",
        "repository_keywords",
        "readme_content",
        "somef_description",
    ],
}


def normalized_record(record: dict[str, Any]) -> dict[str, Any] | None:
    labels = clean_list(record.get("labels"))
    if not labels:
        return None
    output = {field: record.get(field) for field in FINAL_FIELDS}
    output["labels"] = labels
    output["label"] = labels[0] if len(labels) == 1 else None
    output["label_count"] = len(labels)
    output["is_single_label"] = len(labels) == 1
    output["is_multi_label"] = len(labels) > 1
    return output


def coverage_rows(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for source in sorted({record["source"] for record in records}):
        source_records = [record for record in records if record["source"] == source]
        for name, fields in ATTRIBUTE_COMBINATIONS.items():
            count = sum(bool(build_text(record, fields)) for record in source_records)
            rows.append(
                {
                    "source": source,
                    "attribute_set": name,
                    "records_with_text": count,
                    "records": len(source_records),
                    "coverage_percent": count / len(source_records) * 100 if source_records else 0.0,
                }
            )
    return rows


def dataset_overview(single: list[dict[str, Any]], multi_only: list[dict[str, Any]], combined: list[dict[str, Any]]) -> pd.DataFrame:
    datasets = {
        "final_single_label": single,
        "final_multi_label_only": multi_only,
        "final_combined": combined,
    }
    rows = []
    for name, records in datasets.items():
        rows.append(
            {
                "dataset": name,
                "records": len(records),
                "sources": ", ".join(sorted({record["source"] for record in records})),
                "papers_with_code_records": sum(record["source"] == "papers_with_code" for record in records),
                "biotools_records": sum(record["source"] == "bio.tools" for record in records),
                "unique_labels_total": len({label for record in records for label in record["labels"]}),
                "unique_papers_with_code_labels": len({label for record in records if record["source"] == "papers_with_code" for label in record["labels"]}),
                "unique_biotools_labels": len({label for record in records if record["source"] == "bio.tools" for label in record["labels"]}),
                "records_with_readme": sum(bool(record.get("readme_content")) for record in records),
                "records_with_somef_description": sum(bool(record.get("somef_description")) for record in records),
                "records_with_title_or_abstract": sum(bool(record.get("paper_title") or record.get("paper_abstract")) for record in records),
            }
        )
    return pd.DataFrame(rows)


def label_distribution(records: list[dict[str, Any]]) -> pd.DataFrame:
    counters: dict[str, Counter[str]] = defaultdict(Counter)
    for record in records:
        counters[record["source"]].update(record["labels"])
    rows = []
    for source, counter in sorted(counters.items()):
        total = sum(counter.values())
        for label, support in counter.most_common():
            rows.append(
                {
                    "source": source,
                    "label": label,
                    "support": support,
                    "percent_of_source_assignments": support / total * 100 if total else 0.0,
                }
            )
    return pd.DataFrame(rows)


def markdown_table(df: pd.DataFrame, max_rows: int | None = None) -> str:
    if max_rows is not None:
        df = df.head(max_rows)
    if df.empty:
        return "No rows."
    columns = list(df.columns)
    lines = [
        "| " + " | ".join(columns) + " |",
        "| " + " | ".join("---" for _ in columns) + " |",
    ]
    for _, row in df.iterrows():
        lines.append("| " + " | ".join(str(row[col]) for col in columns) + " |")
    return "\n".join(lines)


def write_readme(single: list[dict[str, Any]], multi_only: list[dict[str, Any]], combined: list[dict[str, Any]]) -> None:
    overview = pd.read_csv(OUTPUT_DIR / "dataset_overview.csv")
    labels = pd.read_csv(OUTPUT_DIR / "label_distribution_by_source.csv")
    coverage = pd.read_csv(OUTPUT_DIR / "attribute_coverage.csv")
    biotools_labels = labels[labels["source"].eq("bio.tools")].copy()
    pwc_labels = labels[labels["source"].eq("papers_with_code")].copy()
    readme = f"""# Final Datasets

This folder contains the three final datasets used for the final analysis.
They are built from `data/final_edam_top_level/combined_all_with_somef.jsonl`
and keep only the attributes used by the final metadata-comparison analysis.

## Files

- `final_single_label.jsonl`: records with exactly one target label.
- `final_multi_label_only.jsonl`: records with two or more target labels.
- `final_combined.jsonl`: all final labelled records.
- `dataset_overview.csv`: dataset-level counts.
- `label_distribution_by_source.csv`: label support by source.
- `attribute_coverage.csv`: text availability for each final attribute set.

The single-label file is used for single-only classification experiments. The
multi-label-only file is used for multi-only classification experiments. The
combined file is used for merged classification experiments where single-label
and multi-label records for the same source are evaluated together.

## Schema

Each JSONL row contains:

```text
source, item_id, software_name, software_description, paper_title,
paper_abstract, publication_url, repository_url, repository_title,
repository_description, repository_keywords, readme_content,
somef_description, tasks, methods, secondary_labels, labels, label,
label_count, is_single_label, is_multi_label
```

`labels` is always a list. `label` is filled only for records with exactly one
target label.

## Dataset Overview

{markdown_table(overview)}

## Label Distribution

### Papers with Code

{markdown_table(pwc_labels)}

### bio.tools

{markdown_table(biotools_labels)}

## Attribute Coverage

{markdown_table(coverage)}

## Attribute Sets Used In The Final Analysis

```json
{json.dumps(ATTRIBUTE_COMBINATIONS, indent=2)}
```

## Running The Final Analysis

From the repository root, run:

```bash
poetry run python scripts/run_final_results.py
```

This rebuilds the files in this folder and writes all result tables, figures,
predictions, logs, and reports to `final_results/`.
The analysis trains PwC and bio.tools separately across six datasets:
PwC single-only, PwC multi-only, PwC merged, bio.tools single-only,
bio.tools multi-only, and bio.tools merged.
"""
    (OUTPUT_DIR / "README.md").write_text(readme, encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    combined = [record for record in (normalized_record(row) for row in read_jsonl(SOURCE_DATASET)) if record is not None]
    single = [record for record in combined if record["label_count"] == 1]
    multi_only = [record for record in combined if record["label_count"] > 1]

    write_jsonl(single, SINGLE_JSONL)
    write_jsonl(multi_only, MULTI_ONLY_JSONL)
    write_jsonl(combined, COMBINED_JSONL)

    dataset_overview(single, multi_only, combined).to_csv(OUTPUT_DIR / "dataset_overview.csv", index=False)
    label_distribution(combined).to_csv(OUTPUT_DIR / "label_distribution_by_source.csv", index=False)
    pd.DataFrame(coverage_rows(combined)).to_csv(OUTPUT_DIR / "attribute_coverage.csv", index=False)
    write_readme(single, multi_only, combined)

    print(f"Wrote final datasets to {OUTPUT_DIR}")
    print(dataset_overview(single, multi_only, combined).to_string(index=False))


if __name__ == "__main__":
    main()
