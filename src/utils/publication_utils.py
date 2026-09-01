"""Publication metadata helpers for DOI-based enrichment.

The bio.tools records often provide DOI identifiers without publication titles
or abstracts. This module uses OpenAlex as a public scholarly metadata source,
caches DOI lookups, and reconstructs OpenAlex abstracts from the documented
``abstract_inverted_index`` representation.
"""
from __future__ import annotations

import logging
import os
import re
from typing import Any

import requests

from src import config
from src.utils.text_utils import clean_list, clean_markup_text, clean_text

LOGGER = logging.getLogger(__name__)
DOI_RE = re.compile(r"10\.\d{4,9}/[^\s|;,]+", re.IGNORECASE)


def normalize_doi(value: Any) -> str | None:
    """Return a normalized DOI without URL prefixes or trailing punctuation."""
    text = clean_text(value)
    if not text:
        return None
    text = text.replace("https://doi.org/", "").replace("http://doi.org/", "")
    text = text.replace("doi:", "").strip()
    lowered = text.lower()
    for marker in [".pmid", "pmid:", ".pmcid", "pmcid:"]:
        marker_index = lowered.find(marker)
        if marker_index > 0:
            text = text[:marker_index]
            lowered = text.lower()
    match = DOI_RE.search(text)
    if not match:
        return None
    return match.group(0).rstrip(").,;").lower()


def extract_dois(value: Any) -> list[str]:
    """Extract unique DOI strings from JSON/list/pipe/text fields."""
    dois: list[str] = []
    for item in clean_list(value):
        for match in DOI_RE.findall(item):
            doi = normalize_doi(match)
            if doi and doi not in dois:
                dois.append(doi)
    return dois


def doi_url(doi: str | None) -> str | None:
    """Convert a normalized DOI to a resolvable DOI URL."""
    return f"https://doi.org/{doi}" if doi else None


def abstract_from_inverted_index(index: dict[str, list[int]] | None) -> str | None:
    """Reconstruct an abstract from OpenAlex's inverted-index representation."""
    if not index:
        return None
    positions: dict[int, str] = {}
    for word, word_positions in index.items():
        for position in word_positions:
            positions[int(position)] = word
    if not positions:
        return None
    return clean_markup_text(" ".join(positions[position] for position in sorted(positions)))


def openalex_params() -> dict[str, str]:
    """Return reproducibility-friendly OpenAlex request parameters."""
    params: dict[str, str] = {}
    api_key = os.environ.get(config.OPENALEX_API_KEY_ENV_VAR)
    mailto = os.environ.get(config.OPENALEX_MAILTO_ENV_VAR)
    if api_key:
        params["api_key"] = api_key
    if mailto:
        params["mailto"] = mailto
    return params


def simplify_openalex_work(work: dict[str, Any], requested_doi: str) -> dict[str, Any]:
    """Keep only publication fields needed by the dataset preparation pipeline."""
    openalex_doi = normalize_doi(work.get("doi")) or requested_doi
    return {
        "doi": requested_doi,
        "openalex_id": work.get("id"),
        "openalex_doi": openalex_doi,
        "publication_url": doi_url(openalex_doi),
        "paper_title": clean_markup_text(work.get("title") or work.get("display_name")),
        "paper_abstract": abstract_from_inverted_index(work.get("abstract_inverted_index")),
        "publication_year": work.get("publication_year"),
        "publication_type": work.get("type"),
        "metadata_source": "openalex",
        "metadata_error": None,
    }


def fetch_openalex_batch(dois: list[str], session: requests.Session | None = None) -> dict[str, dict[str, Any]]:
    """Fetch a batch of DOI records from OpenAlex using its DOI OR filter."""
    if not dois:
        return {}
    owns_session = session is None
    if session is None:
        session = requests.Session()
    try:
        params = {
            **openalex_params(),
            "filter": "doi:" + "|".join(dois),
            "per_page": str(max(len(dois), 1)),
            "select": "id,doi,title,display_name,abstract_inverted_index,publication_year,type",
        }
        response = session.get(
            f"{config.OPENALEX_API_BASE}/works",
            params=params,
            timeout=config.OPENALEX_REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        payload = response.json()
        results: dict[str, dict[str, Any]] = {}
        for work in payload.get("results", []):
            found_doi = normalize_doi(work.get("doi"))
            if found_doi:
                results[found_doi] = simplify_openalex_work(work, found_doi)
        for doi in dois:
            results.setdefault(
                doi,
                {
                    "doi": doi,
                    "publication_url": doi_url(doi),
                    "paper_title": None,
                    "paper_abstract": None,
                    "metadata_source": "openalex",
                    "metadata_error": "not_found",
                },
            )
        return results
    except requests.RequestException as exc:
        LOGGER.warning("OpenAlex DOI batch failed: %s", exc)
        return {
            doi: {
                "doi": doi,
                "publication_url": doi_url(doi),
                "paper_title": None,
                "paper_abstract": None,
                "metadata_source": "openalex",
                "metadata_error": str(exc),
            }
            for doi in dois
        }
    finally:
        if owns_session:
            session.close()
