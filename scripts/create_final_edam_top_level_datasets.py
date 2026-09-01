#!/usr/bin/env python3
"""Create final analysis datasets with bio.tools labels mapped to EDAM top level.

Papers with Code records are copied unchanged. bio.tools records keep their
original detailed EDAM labels in ``raw_labels``/``raw_label_uris`` and replace
``labels`` with the highest meaningful EDAM topic labels below the EDAM Topic
root. This creates final full-dataset inputs for analysis and training without
overwriting the detailed-label files in ``data/final``.
"""
from __future__ import annotations

import logging
import shutil
import sys
from collections import Counter
from pathlib import Path
from typing import Any

import pandas as pd

sys.path.append(str(Path(__file__).resolve().parent.parent))
sys.path.append(str(Path(__file__).resolve().parent))

import map_biotools_edam_to_top_level as edam_mapping
from src import config
from src.utils.io_utils import configure_logging, read_jsonl, write_csv, write_jsonl
from src.utils.text_utils import clean_list


OUTPUT_DIR = config.DATA_DIR / "final_edam_top_level"
LOG_PATH = config.RESULTS_DIR / "logs" / "final_edam_top_level_dataset.log"
SUMMARY_CSV = OUTPUT_DIR / "dataset_filtering_summary.csv"
LABEL_DISTRIBUTION_CSV = OUTPUT_DIR / "biotools_top_level_label_distribution.csv"

DATASET_PATHS = {
    "pwc_single_label": config.PWC_SINGLE_LABEL_JSONL,
    "pwc_multi_label": config.PWC_MULTI_LABEL_JSONL,
    "pwc_single_label_with_somef": config.PWC_SINGLE_LABEL_WITH_SOMEF_JSONL,
    "pwc_multi_label_with_somef": config.PWC_MULTI_LABEL_WITH_SOMEF_JSONL,
    "biotools_multi_label": config.BIOTOOLS_MULTI_LABEL_JSONL,
    "biotools_multi_label_with_somef": config.BIOTOOLS_MULTI_LABEL_WITH_SOMEF_JSONL,
}

LOGGER = logging.getLogger("create_final_edam_top_level_datasets")


def configure_script_logging() -> None:
    configure_logging()
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    root_logger = logging.getLogger()
    if not any(isinstance(handler, logging.FileHandler) and handler.baseFilename == str(LOG_PATH) for handler in root_logger.handlers):
        handler = logging.FileHandler(LOG_PATH, encoding="utf-8")
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s", datefmt="%Y-%m-%d %H:%M:%S"))
        root_logger.addHandler(handler)


def output_path(name: str) -> Path:
    return OUTPUT_DIR / f"{name}.jsonl"


def copy_pwc_datasets() -> list[dict[str, Any]]:
    rows = []
    for name in ["pwc_single_label", "pwc_multi_label", "pwc_single_label_with_somef", "pwc_multi_label_with_somef"]:
        source = DATASET_PATHS[name]
        target = output_path(name)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        rows.append({"dataset": name, "source_records": sum(1 for _ in read_jsonl(source)), "output_records": sum(1 for _ in read_jsonl(target)), "mapping": "copied_unchanged"})
    return rows


def load_mapping_resources() -> tuple[dict[str, Any], pd.DataFrame, dict[str, dict[str, list[str]]]]:
    ontology_path, _ = edam_mapping.ensure_edam_ontology()
    ontology = edam_mapping.parse_edam_topics(ontology_path)
    label_mapping_table = edam_mapping.build_topic_mapping(ontology)
    raw_lookup = edam_mapping.load_raw_topic_lookup()
    return ontology, label_mapping_table, raw_lookup


def normalize_label_field(record: dict[str, Any], label_setting: str) -> dict[str, Any]:
    row = dict(record)
    labels = clean_list(row.get("labels"))
    if label_setting == "single":
        row["labels"] = labels
        row["label"] = labels[0] if len(labels) == 1 else None
    else:
        row["labels"] = labels
        row["label"] = labels
    return row


def map_biotools_dataset(
    name: str,
    ontology: dict[str, Any],
    label_mapping_table: pd.DataFrame,
    raw_lookup: dict[str, dict[str, list[str]]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    source = DATASET_PATHS[name]
    records = list(read_jsonl(source))
    mapped_records, unmapped, excluded = edam_mapping.map_records(records, ontology, label_mapping_table, raw_lookup)
    mapped_records = [normalize_label_field(record, "multi") for record in mapped_records if clean_list(record.get("labels"))]
    write_jsonl(mapped_records, output_path(name))
    write_csv(mapped_records, OUTPUT_DIR / f"{name}.csv")
    summary = {
        "dataset": name,
        "source_records": len(records),
        "mapped_before_label_setting_filter": len(records),
        "output_records": len(mapped_records),
        "mapping": "biotools_edam_top_level",
        "unique_output_labels": len({label for record in mapped_records for label in clean_list(record.get("labels"))}),
        "unmapped_label_rows": len(unmapped),
        "excluded_generic_label_rows": len(excluded),
    }
    return mapped_records, summary


def write_biotools_single_from_multi(name: str, source_records: list[dict[str, Any]]) -> dict[str, Any]:
    single_records = [
        normalize_label_field(record, "single")
        for record in source_records
        if len(clean_list(record.get("labels"))) == 1
    ]
    write_jsonl(single_records, output_path(name))
    write_csv(single_records, OUTPUT_DIR / f"{name}.csv")
    return {
        "dataset": name,
        "source_records": len(source_records),
        "mapped_before_label_setting_filter": len(source_records),
        "output_records": len(single_records),
        "mapping": "biotools_edam_top_level_single_from_mapped_multi",
        "unique_output_labels": len({label for record in single_records for label in clean_list(record.get("labels"))}),
        "unmapped_label_rows": 0,
        "excluded_generic_label_rows": 0,
    }


def combine_datasets(names: list[str], output_name: str) -> dict[str, Any]:
    combined: list[dict[str, Any]] = []
    for name in names:
        combined.extend(read_jsonl(output_path(name)))
    write_jsonl(combined, output_path(output_name))
    write_csv(combined, OUTPUT_DIR / f"{output_name}.csv")
    return {
        "dataset": output_name,
        "source_records": sum(sum(1 for _ in read_jsonl(output_path(name))) for name in names),
        "output_records": len(combined),
        "mapping": "combined",
        "unique_output_labels": len({label for record in combined for label in clean_list(record.get("labels"))}),
    }


def write_label_distribution(records: list[dict[str, Any]]) -> None:
    counter: Counter[str] = Counter()
    for record in records:
        counter.update(clean_list(record.get("labels")))
    total = sum(counter.values())
    rows = [
        {"label": label, "support": count, "percent_of_assignments": count / total * 100 if total else 0.0}
        for label, count in counter.most_common()
    ]
    pd.DataFrame(rows).to_csv(LABEL_DISTRIBUTION_CSV, index=False)


def main() -> None:
    configure_script_logging()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    LOGGER.info("Creating final EDAM top-level datasets in %s", OUTPUT_DIR)
    summary_rows = copy_pwc_datasets()
    ontology, label_mapping_table, raw_lookup = load_mapping_resources()
    biotools_multi, summary = map_biotools_dataset("biotools_multi_label", ontology, label_mapping_table, raw_lookup)
    summary_rows.append(summary)
    summary_rows.append(write_biotools_single_from_multi("biotools_single_label", biotools_multi))
    biotools_multi_with_somef, summary = map_biotools_dataset("biotools_multi_label_with_somef", ontology, label_mapping_table, raw_lookup)
    summary_rows.append(summary)
    summary_rows.append(write_biotools_single_from_multi("biotools_single_label_with_somef", biotools_multi_with_somef))
    summary_rows.append(combine_datasets(["pwc_multi_label", "biotools_multi_label"], "combined_all"))
    summary_rows.append(combine_datasets(["pwc_multi_label_with_somef", "biotools_multi_label_with_somef"], "combined_all_with_somef"))
    pd.DataFrame(summary_rows).to_csv(SUMMARY_CSV, index=False)
    write_label_distribution(biotools_multi_with_somef)
    LOGGER.info("Final EDAM top-level datasets complete")
    print(pd.DataFrame(summary_rows).to_string(index=False))


if __name__ == "__main__":
    main()
