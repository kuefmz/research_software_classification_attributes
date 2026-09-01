#!/usr/bin/env python3
"""Train early ML baselines on bio.tools EDAM top-level labels.

This wrapper reuses the standard early-subset training pipeline while pointing
it at the mapped bio.tools analysis output. Results and train/test splits are
kept in separate folders so they do not overwrite or reuse the combined
early-subset experiments.
"""
from __future__ import annotations

import early_subset_training_pipeline as training
from src import config


INPUT_DATASET = (
    config.RESULTS_DIR
    / "early_subset_biotools_top_level_analysis"
    / "biotools_top_level_enriched_records.jsonl"
)
RESULTS_DIR = config.RESULTS_DIR / "early_subset_biotools_top_level_training"
SPLITS_DIR = config.SPLITS_DIR / "early_subset_biotools_top_level"


def main() -> None:
    """Configure and run the shared training pipeline for mapped bio.tools labels."""
    training.ANALYSIS_STAGE = "early_subset_biotools_edam_top_level"
    training.INPUT_DATASET = INPUT_DATASET
    training.RESULTS_DIR = RESULTS_DIR
    training.SPLITS_DIR = SPLITS_DIR
    training.LOG_PATH = RESULTS_DIR / "early_subset_biotools_top_level_training.log"
    training.SUMMARY_CSV = RESULTS_DIR / "summary_results.csv"
    training.PER_CLASS_CSV = RESULTS_DIR / "per_class_results.csv"
    training.SKIPPED_CSV = RESULTS_DIR / "skipped_experiments.csv"
    training.PREDICTIONS_JSONL = RESULTS_DIR / "predictions.jsonl"
    training.RESULTS_XLSX = RESULTS_DIR / "biotools_top_level_training_results.xlsx"
    training.PACKAGE_VERSIONS_JSON = RESULTS_DIR / "package_versions.json"
    training.CONFIG_JSON = RESULTS_DIR / "run_configuration.json"
    training.PROMPTS_DIR = RESULTS_DIR / "prompt_templates"
    training.main()


if __name__ == "__main__":
    main()
