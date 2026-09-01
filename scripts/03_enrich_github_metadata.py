#!/usr/bin/env python3
"""Enrich aligned records with cached GitHub metadata and README content."""
from __future__ import annotations

import logging
import sys
from pathlib import Path

import requests

try:
    from tqdm import tqdm
except ImportError:  # pragma: no cover - keeps the script usable before dependency install.
    def tqdm(iterable, **_: object):
        return iterable

sys.path.append(str(Path(__file__).resolve().parent.parent))

from src import config
from src.utils.github_utils import fetch_repository_metadata, github_headers, normalize_github_url
from src.utils.io_utils import configure_logging, read_jsonl, write_jsonl

LOGGER = logging.getLogger("enrich_github")


def _load_inputs() -> list[dict]:
    records: list[dict] = []
    biotools_path = (
        config.BIOTOOLS_PUBLICATION_ENRICHED_JSONL
        if config.BIOTOOLS_PUBLICATION_ENRICHED_JSONL.exists()
        else config.BIOTOOLS_ALIGNED_JSONL
    )
    for path in [config.PWC_ALIGNED_JSONL, biotools_path]:
        if path.exists():
            records.extend(read_jsonl(path))
        else:
            LOGGER.warning("Skipping missing aligned file: %s", path)
    return records


def _load_cache() -> dict[str, dict]:
    if not config.GITHUB_CACHE_JSONL.exists():
        return {}
    cache: dict[str, dict] = {}
    for row in read_jsonl(config.GITHUB_CACHE_JSONL):
        key = row.get("repository_url_normalized") or normalize_github_url(row.get("repository_url"))
        if key:
            cache[key] = row
    return cache


def main() -> None:
    configure_logging()
    config.ensure_directories()
    records = _load_inputs()
    LOGGER.info("Loaded aligned records: %s", f"{len(records):,}")
    cache = _load_cache()
    LOGGER.info("Loaded cached repositories: %s", f"{len(cache):,}")

    repository_urls = []
    for record in records:
        for url in [record.get("repository_url"), *(record.get("repository_urls") or [])]:
            normalized = normalize_github_url(url)
            if normalized and normalized not in repository_urls:
                repository_urls.append(normalized)
    LOGGER.info("Unique GitHub repositories in aligned data: %s", f"{len(repository_urls):,}")

    with requests.Session() as session:
        session.headers.update(github_headers())
        for normalized_url in tqdm(repository_urls, desc="Fetching GitHub metadata"):
            if normalized_url in cache:
                continue
            cache[normalized_url] = fetch_repository_metadata(normalized_url, session=session)

    cache_records = [cache[key] for key in sorted(cache)]
    write_jsonl(cache_records, config.GITHUB_CACHE_JSONL)
    LOGGER.info("Wrote GitHub cache: %s", config.GITHUB_CACHE_JSONL)

    enriched = []
    for record in records:
        normalized = normalize_github_url(record.get("repository_url"))
        github = cache.get(normalized) if normalized else None
        row = dict(record)
        if github:
            row.update(github)
        enriched.append(row)
    write_jsonl(enriched, config.GITHUB_ENRICHED_JSONL)
    LOGGER.info("Wrote GitHub-enriched records: %s", config.GITHUB_ENRICHED_JSONL)


if __name__ == "__main__":
    main()
