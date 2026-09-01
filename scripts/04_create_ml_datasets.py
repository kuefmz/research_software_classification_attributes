#!/usr/bin/env python3
"""Create final single-label and multi-label ML-ready JSONL datasets."""
from __future__ import annotations

import logging
import sys
from pathlib import Path

try:
    from tqdm import tqdm
except ImportError:  # pragma: no cover - keeps the script usable before dependency install.
    def tqdm(iterable, **_: object):
        return iterable

sys.path.append(str(Path(__file__).resolve().parent.parent))

from src import config
from src.utils.dataset_utils import final_record, labels_without_exclusions, merge_enrichment
from src.utils.github_utils import normalize_github_url
from src.utils.io_utils import configure_logging, log_count_change, read_jsonl, write_csv, write_jsonl
from src.utils.publication_utils import normalize_doi

LOGGER = logging.getLogger("create_ml_datasets")


def _load_aligned_or_enriched() -> list[dict]:
    if config.GITHUB_ENRICHED_JSONL.exists():
        LOGGER.info("Reading GitHub-enriched records from %s", config.GITHUB_ENRICHED_JSONL)
        return list(read_jsonl(config.GITHUB_ENRICHED_JSONL))

    records: list[dict] = []
    biotools_path = (
        config.BIOTOOLS_PUBLICATION_ENRICHED_JSONL
        if config.BIOTOOLS_PUBLICATION_ENRICHED_JSONL.exists()
        else config.BIOTOOLS_ALIGNED_JSONL
    )
    for path in [config.PWC_ALIGNED_JSONL, biotools_path]:
        if path.exists():
            LOGGER.info("Reading records from %s", path)
            records.extend(read_jsonl(path))
        else:
            LOGGER.warning("Skipping missing aligned file: %s", path)
    return records


def _load_somef_cache() -> dict[str, dict]:
    if not config.SOMEF_CACHE_JSONL.exists():
        return {}
    return {
        row["repository_url_normalized"]: row
        for row in read_jsonl(config.SOMEF_CACHE_JSONL)
        if row.get("repository_url_normalized")
    }


def _ensure_somef(records: list[dict]) -> dict[str, dict]:
    if not config.RUN_SOMEF_ENRICHMENT:
        LOGGER.info("Skipping SoMEF enrichment because RUN_SOMEF_ENRICHMENT=False")
        return {}

    from src.utils.somef_utils import extract_somef_from_readme

    cache = _load_somef_cache()
    for record in tqdm(records, desc="SoMEF README extraction"):
        normalized = record.get("repository_url_normalized") or normalize_github_url(record.get("repository_url"))
        readme_content = record.get("readme_content")
        if not normalized or normalized in cache or not readme_content:
            continue
        result = extract_somef_from_readme(readme_content)
        cache[normalized] = {"repository_url_normalized": normalized, **result}
    write_jsonl([cache[key] for key in sorted(cache)], config.SOMEF_CACHE_JSONL)
    return cache


def _write_dataset(records: list[dict], source: str, label_mode: str, path: Path) -> None:
    source_records = [record for record in records if record.get("source") == source]
    before = len(source_records)
    final_records = [row for row in (final_record(record, label_mode) for record in source_records) if row is not None]
    log_count_change(LOGGER, f"{path.name} {label_mode} label filter", before, len(final_records))
    write_jsonl(final_records, path)


def _log_filter(summary: list[dict], step: str, before: int, after: int) -> None:
    log_count_change(LOGGER, step, before, after)
    summary.append({"step": step, "before": before, "after": after, "removed": before - after})


def _clean_labels(records: list[dict], summary: list[dict]) -> list[dict]:
    cleaned = []
    changed = 0
    for record in records:
        labels = labels_without_exclusions(record)
        if labels != (record.get("labels") or []):
            changed += 1
        row = dict(record)
        row["labels"] = labels
        cleaned.append(row)
    LOGGER.info("Removed source-specific excluded labels from %s records", f"{changed:,}")
    summary.append({"step": "remove excluded labels", "before": len(records), "after": len(records), "removed": 0})
    return cleaned


def _clean_usable_records(records: list[dict]) -> tuple[list[dict], list[dict]]:
    summary: list[dict] = []
    before = len(records)
    records = _clean_labels(records, summary)

    before = len(records)
    records = [record for record in records if record.get("labels")]
    _log_filter(summary, "drop records with no labels after cleanup", before, len(records))

    before = len(records)
    records = [
        {**record, "repository_url_normalized": normalize_github_url(record.get("repository_url"))}
        for record in records
        if normalize_github_url(record.get("repository_url"))
    ]
    _log_filter(summary, "drop records without GitHub repository URL", before, len(records))

    before = len(records)
    records = [
        record
        for record in records
        if record.get("source") != "bio.tools" or normalize_doi(record.get("doi") or record.get("publication_url"))
    ]
    _log_filter(summary, "drop bio.tools records without DOI", before, len(records))
    return records, summary


def main() -> None:
    configure_logging()
    config.ensure_directories()
    records = _load_aligned_or_enriched()
    LOGGER.info("Loaded input records: %s", f"{len(records):,}")
    records, summary = _clean_usable_records(records)
    LOGGER.info("Usable records after cleanup: %s", f"{len(records):,}")
    somef_cache = _ensure_somef(records)
    enriched_records = []
    for record in records:
        normalized = record.get("repository_url_normalized") or normalize_github_url(record.get("repository_url"))
        enriched_records.append(merge_enrichment(record, record, somef_cache.get(normalized) if normalized else None))

    _write_dataset(enriched_records, "papers_with_code", "single", config.PWC_SINGLE_LABEL_JSONL)
    _write_dataset(enriched_records, "papers_with_code", "multi", config.PWC_MULTI_LABEL_JSONL)
    _write_dataset(enriched_records, "bio.tools", "single", config.BIOTOOLS_SINGLE_LABEL_JSONL)
    _write_dataset(enriched_records, "bio.tools", "multi", config.BIOTOOLS_MULTI_LABEL_JSONL)
    write_jsonl(enriched_records, config.COMBINED_ALL_JSONL)
    write_csv(summary, config.DATASET_FILTERING_SUMMARY_CSV, ["step", "before", "after", "removed"])
    LOGGER.info("Wrote combined aligned/enriched dataset: %s", config.COMBINED_ALL_JSONL)
    LOGGER.info("Wrote filtering summary: %s", config.DATASET_FILTERING_SUMMARY_CSV)


if __name__ == "__main__":
    main()
