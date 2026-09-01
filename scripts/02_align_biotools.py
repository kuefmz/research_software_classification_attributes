#!/usr/bin/env python3
"""Align bio.tools data to the shared Papers with Code-compatible schema."""
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
from src.utils.github_utils import normalize_github_url
from src.utils.io_utils import configure_logging, read_csv_dicts, read_jsonl, write_csv, write_jsonl
from src.utils.publication_utils import doi_url, extract_dois, normalize_doi
from src.utils.text_utils import clean_list, clean_text

LOGGER = logging.getLogger("align_biotools")


def _publication_url(row: dict[str, Any], doi: str | None = None) -> str | None:
    if doi:
        return doi_url(doi)
    dois = clean_list(row.get("doi"))
    pmids = clean_list(row.get("pmid"))
    pmcids = clean_list(row.get("pmcid"))
    if dois:
        doi = dois[0].replace("https://doi.org/", "")
        return f"https://doi.org/{doi}"
    if pmids:
        return f"https://pubmed.ncbi.nlm.nih.gov/{pmids[0]}/"
    if pmcids:
        return f"https://www.ncbi.nlm.nih.gov/pmc/articles/{pmcids[0]}/"
    return None


def _operation_terms_from_raw(tool: dict[str, Any]) -> list[str]:
    terms: list[str] = []
    for function in tool.get("function") or []:
        if not isinstance(function, dict):
            continue
        for operation in function.get("operation") or []:
            if isinstance(operation, dict):
                terms.append(operation.get("term"))
    return clean_list(terms)


def _github_from_raw(tool: dict[str, Any]) -> str | None:
    candidates = [tool.get("homepage")]
    for field in ("link", "download", "documentation"):
        for item in tool.get(field) or []:
            if isinstance(item, dict):
                candidates.append(item.get("url"))
    for candidate in candidates:
        normalized = normalize_github_url(candidate)
        if normalized:
            return normalized
    return None


def align_flat_row(row: dict[str, Any], raw_tool: dict[str, Any] | None = None, doi: str | None = None) -> dict[str, Any]:
    """Map one flattened bio.tools row and one DOI into the shared schema."""
    raw_tool = raw_tool or {}
    repository_url = (
        normalize_github_url(row.get("github_url"))
        or _github_from_raw(raw_tool)
        or clean_text(row.get("github_url"))
    )
    operations = (
        _operation_terms_from_raw(raw_tool)
        or clean_list(row.get("operation_terms") or row.get("edam_operation_terms"))
        or clean_list(row.get("function_text"))
    )
    item_id = row.get("biotools_id")
    if doi:
        item_id = f"{item_id}::doi::{doi}"
    record = schema_record(
        source="bio.tools",
        item_id=item_id,
        software_name=row.get("name"),
        software_description=row.get("description"),
        paper_title=row.get("paper_title") or row.get("publication_note"),
        paper_abstract=row.get("abstract"),
        publication_url=_publication_url(row, doi),
        repository_url=repository_url,
        repository_urls=[repository_url] if repository_url else [],
        labels=row.get("topic_terms"),
        secondary_labels=operations,
        tasks=operations,
        methods=[],
    )
    record["doi"] = doi
    return record


def expand_flat_row(row: dict[str, Any], raw_tool: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """Create one aligned bio.tools record per DOI when multiple DOIs exist."""
    dois = extract_dois(row.get("doi"))
    if not dois and raw_tool:
        publications = raw_tool.get("publication") or []
        dois = [doi for doi in (normalize_doi(pub.get("doi")) for pub in publications if isinstance(pub, dict)) if doi]
    if not dois:
        return [align_flat_row(row, raw_tool, doi=None)]
    return [align_flat_row(row, raw_tool, doi=doi) for doi in dois]


def align_raw_tool(tool: dict[str, Any]) -> dict[str, Any]:
    """Map a raw bio.tools API record into the shared schema."""
    topics = [topic.get("term") for topic in tool.get("topic") or [] if isinstance(topic, dict)]
    operations = _operation_terms_from_raw(tool)
    publications = tool.get("publication") or []
    first_publication = publications[0] if publications and isinstance(publications[0], dict) else {}
    doi = normalize_doi(first_publication.get("doi"))
    row = {
        "doi": first_publication.get("doi"),
        "pmid": first_publication.get("pmid"),
        "pmcid": first_publication.get("pmcid"),
    }
    repository_url = _github_from_raw(tool)
    record = schema_record(
        source="bio.tools",
        item_id=f"{tool.get('biotoolsID')}::doi::{doi}" if doi else tool.get("biotoolsID"),
        software_name=tool.get("name"),
        software_description=tool.get("description"),
        paper_title=(first_publication.get("metadata") or {}).get("title") if isinstance(first_publication.get("metadata"), dict) else first_publication.get("note"),
        paper_abstract=(first_publication.get("metadata") or {}).get("abstract") if isinstance(first_publication.get("metadata"), dict) else None,
        publication_url=_publication_url(row, doi),
        repository_url=repository_url,
        repository_urls=[repository_url] if repository_url else [],
        labels=topics,
        secondary_labels=operations,
        tasks=operations,
        methods=[],
    )
    record["doi"] = doi
    return record


def main() -> None:
    configure_logging()
    config.ensure_directories()
    if config.BIOTOOLS_FLAT_CSV.exists():
        LOGGER.info("Reading flattened bio.tools data from %s", config.BIOTOOLS_FLAT_CSV)
        raw_by_id: dict[str, dict[str, Any]] = {}
        if config.BIOTOOLS_RAW_JSONL.exists():
            raw_by_id = {
                row.get("biotoolsID"): row
                for row in read_jsonl(config.BIOTOOLS_RAW_JSONL)
                if row.get("biotoolsID")
            }
            LOGGER.info("Loaded raw bio.tools lookup records: %s", f"{len(raw_by_id):,}")
        records = []
        for row in tqdm(read_csv_dicts(config.BIOTOOLS_FLAT_CSV), desc="Aligning bio.tools"):
            records.extend(expand_flat_row(row, raw_by_id.get(row.get("biotools_id"))))
    else:
        LOGGER.info("Reading raw bio.tools JSONL from %s", config.BIOTOOLS_RAW_JSONL)
        records = [align_raw_tool(row) for row in tqdm(read_jsonl(config.BIOTOOLS_RAW_JSONL), desc="Aligning bio.tools")]
    LOGGER.info("Coverage: %s", coverage_counts(records))
    write_jsonl(records, config.BIOTOOLS_ALIGNED_JSONL)
    write_csv(records, config.BIOTOOLS_ALIGNED_CSV, [*config.SCHEMA_FIELDS, *config.BIOTOOLS_EXTRA_FIELDS])
    LOGGER.info("Wrote %s and %s", config.BIOTOOLS_ALIGNED_JSONL, config.BIOTOOLS_ALIGNED_CSV)


if __name__ == "__main__":
    main()
