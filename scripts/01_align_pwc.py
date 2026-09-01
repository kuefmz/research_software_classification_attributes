#!/usr/bin/env python3
"""Align the merged Papers with Code data to the shared schema."""
from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Any

try:
    from tqdm import tqdm
except ImportError:  # pragma: no cover - keeps the script usable before dependency install.
    def tqdm(iterable, **_: object):
        return iterable

sys.path.append(str(Path(__file__).resolve().parent.parent))

from src import config
from src.utils.dataset_utils import coverage_counts, schema_record
from src.utils.io_utils import configure_logging, read_jsonl, write_csv, write_jsonl
from src.utils.publication_utils import extract_dois
from src.utils.text_utils import clean_list, clean_text, stable_id

LOGGER = logging.getLogger("align_pwc")


def _category(record: dict[str, Any], name: str) -> Any:
    categories = record.get("papers with code categories") or {}
    if isinstance(categories, dict):
        return categories.get(name)
    return None


def _methods(record: dict[str, Any]) -> list[str]:
    methods: list[str] = []
    for method in _category(record, "methods") or []:
        if isinstance(method, dict):
            methods.append(method.get("method") or method.get("method_full_name") or method.get("name"))
        else:
            methods.append(method)
    return clean_list(methods)


def align_record(record: dict[str, Any]) -> dict[str, Any]:
    """Map one merged PwC record into the project-wide schema."""
    publication_url = clean_text(record.get("url_abs")) or clean_text(record.get("paper_url")) or clean_text(record.get("url_pdf"))
    repository_urls = clean_list(record.get("github_repos"))
    repository_url = clean_text(record.get("github_repo")) or (repository_urls[0] if repository_urls else None)
    labels = clean_list(record.get("main_collection_areas") or record.get("main_collection_area") or _category(record, "main_collection_areas"))
    item_id = stable_id("papers_with_code", record.get("paper_title"), publication_url)
    doi_candidates = []
    for field in ["doi", "paper_url", "url_abs", "url_pdf", "publication_url"]:
        doi_candidates.extend(extract_dois(record.get(field)))
    aligned = schema_record(
        source="papers_with_code",
        item_id=item_id,
        software_name=None,
        software_description=None,
        paper_title=record.get("paper_title"),
        paper_abstract=record.get("abstract") or record.get("short_abstract"),
        publication_url=publication_url,
        repository_url=repository_url,
        repository_urls=repository_urls,
        labels=labels,
        secondary_labels=_category(record, "collections"),
        tasks=_category(record, "tasks"),
        methods=_methods(record),
    )
    aligned["doi"] = doi_candidates[0] if doi_candidates else None
    aligned["arxiv_id"] = clean_text(record.get("arxiv_id"))
    return aligned


def main() -> None:
    configure_logging()
    config.ensure_directories()
    LOGGER.info("Reading merged PwC records from %s", config.PWC_MERGED_JSONL)
    raw_records = list(read_jsonl(config.PWC_MERGED_JSONL))
    LOGGER.info("Loaded raw PwC records: %s", f"{len(raw_records):,}")
    records = [align_record(record) for record in tqdm(raw_records, desc="Aligning PwC")]
    LOGGER.info("Coverage: %s", coverage_counts(records))
    write_jsonl(records, config.PWC_ALIGNED_JSONL)
    write_csv(records, config.PWC_ALIGNED_CSV, [*config.SCHEMA_FIELDS, *config.BIOTOOLS_EXTRA_FIELDS, "arxiv_id"])
    LOGGER.info("Wrote %s and %s", config.PWC_ALIGNED_JSONL, config.PWC_ALIGNED_CSV)


if __name__ == "__main__":
    main()
