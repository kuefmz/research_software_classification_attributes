#!/usr/bin/env python3
"""Enrich bio.tools DOI rows with public publication metadata from OpenAlex.

The script reads ``data/intermediate/biotools/biotools_aligned.jsonl``. Records
with DOI values are looked up in OpenAlex in deterministic batches and cached in
``openalex_publication_cache.jsonl``. The output keeps one record per bio.tools
tool/DOI pair and fills ``paper_title`` and ``paper_abstract`` when OpenAlex has
the metadata.
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

import requests

try:
    from tqdm import tqdm
except ImportError:  # pragma: no cover
    def tqdm(iterable, **_: object):
        return iterable

sys.path.append(str(Path(__file__).resolve().parent.parent))

from src import config
from src.utils.io_utils import configure_logging, read_jsonl, write_csv, write_jsonl
from src.utils.publication_utils import extract_dois, fetch_openalex_batch, normalize_doi
from src.utils.text_utils import clean_markup_text, clean_text

LOGGER = logging.getLogger("enrich_biotools_publications")


def _load_cache() -> dict[str, dict]:
    if not config.BIOTOOLS_PUBLICATION_CACHE_JSONL.exists():
        return {}
    return {
        row["doi"]: row
        for row in read_jsonl(config.BIOTOOLS_PUBLICATION_CACHE_JSONL)
        if row.get("doi")
    }


def _should_retry(metadata: dict | None) -> bool:
    """Retry transient/network failures but keep confirmed not-found records."""
    if not metadata:
        return True
    error = metadata.get("metadata_error")
    return bool(error and error != "not_found")


def _record_doi(record: dict) -> str | None:
    doi = normalize_doi(record.get("doi"))
    if doi:
        return doi
    dois = extract_dois(record.get("publication_url"))
    return dois[0] if dois else None


def _batches(values: list[str], size: int) -> list[list[str]]:
    return [values[index : index + size] for index in range(0, len(values), size)]


def main() -> None:
    configure_logging()
    config.ensure_directories()
    records = list(read_jsonl(config.BIOTOOLS_ALIGNED_JSONL))
    LOGGER.info("Loaded aligned bio.tools records: %s", f"{len(records):,}")

    dois = sorted({doi for doi in (_record_doi(record) for record in records) if doi})
    LOGGER.info("Unique DOI values to enrich: %s", f"{len(dois):,}")

    cache = _load_cache()
    missing = [doi for doi in dois if _should_retry(cache.get(doi))]
    LOGGER.info("OpenAlex DOI cache: cached=%s missing=%s", f"{len(cache):,}", f"{len(missing):,}")

    with requests.Session() as session:
        for batch in tqdm(_batches(missing, config.OPENALEX_BATCH_SIZE), desc="OpenAlex DOI batches"):
            cache.update(fetch_openalex_batch(batch, session=session))

    write_jsonl([cache[key] for key in sorted(cache)], config.BIOTOOLS_PUBLICATION_CACHE_JSONL)
    LOGGER.info("Wrote publication cache: %s", config.BIOTOOLS_PUBLICATION_CACHE_JSONL)

    enriched = []
    for record in records:
        doi = _record_doi(record)
        metadata = cache.get(doi) if doi else None
        row = dict(record)
        row["doi"] = doi
        if metadata:
            if clean_text(metadata.get("paper_title")):
                row["paper_title"] = clean_markup_text(metadata["paper_title"])
            if clean_text(metadata.get("paper_abstract")):
                row["paper_abstract"] = clean_markup_text(metadata["paper_abstract"])
            for field in [
                "publication_url",
                "metadata_source",
                "metadata_error",
                "publication_year",
                "publication_type",
                "openalex_id",
            ]:
                row[field] = metadata.get(field)
        enriched.append(row)

    with_title = sum(bool(record.get("paper_title")) for record in enriched)
    with_abstract = sum(bool(record.get("paper_abstract")) for record in enriched)
    LOGGER.info("Publication metadata coverage: title=%s abstract=%s", f"{with_title:,}", f"{with_abstract:,}")
    write_jsonl(enriched, config.BIOTOOLS_PUBLICATION_ENRICHED_JSONL)
    write_csv(enriched, config.BIOTOOLS_PUBLICATION_ENRICHED_CSV, [*config.SCHEMA_FIELDS, *config.BIOTOOLS_EXTRA_FIELDS])
    LOGGER.info("Wrote enriched bio.tools publication data: %s", config.BIOTOOLS_PUBLICATION_ENRICHED_JSONL)


if __name__ == "__main__":
    main()
