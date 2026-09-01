#!/usr/bin/env python3
"""Run early subset analysis for bio.tools records with EDAM top-level labels.

This wrapper keeps the original combined early-subset analysis reproducible and
unchanged. It reuses the shared analysis functions, but points them at the
bio.tools dataset produced by ``map_biotools_edam_to_top_level.py`` so the
saved descriptive statistics reflect the EDAM top-level labels that will be
used for the early ML experiments.
"""
from __future__ import annotations

from pathlib import Path

import early_subset_data_analysis as analysis
from src import config


INPUT_DATASET = config.BASE_DIR / "data" / "final_analysis" / "biotools_aligned_top_level_labels.jsonl"
OUTPUT_DIR = config.RESULTS_DIR / "early_subset_biotools_top_level_analysis"


def main() -> None:
    """Configure the shared analysis module for mapped bio.tools labels."""
    analysis.ANALYSIS_STAGE = "early_subset_biotools_edam_top_level"
    analysis.INPUT_DATASET_PATHS = [INPUT_DATASET]
    analysis.OUTPUT_DIR = OUTPUT_DIR
    analysis.OUTPUT_DATA_JSONL = OUTPUT_DIR / "biotools_top_level_enriched_records.jsonl"
    analysis.OUTPUT_DATA_CSV = OUTPUT_DIR / "biotools_top_level_enriched_records.csv"
    analysis.OUTPUT_EXCEL = OUTPUT_DIR / "biotools_top_level_dataset_statistics.xlsx"
    analysis.OUTPUT_REPORT = OUTPUT_DIR / "BIOTOOLS_TOP_LEVEL_EARLY_SUBSET_ANALYSIS_REPORT.md"
    analysis.LOG_PATH = OUTPUT_DIR / "early_subset_biotools_top_level_analysis.log"
    analysis.main()


if __name__ == "__main__":
    main()
