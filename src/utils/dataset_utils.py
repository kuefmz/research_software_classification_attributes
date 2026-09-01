"""Dataset schema alignment and final ML dataset helpers."""
from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from src import config
from src.utils.text_utils import clean_list, clean_markup_text, clean_text


def schema_record(**values: Any) -> dict[str, Any]:
    """Return a record in the shared Papers with Code / bio.tools schema."""
    record: dict[str, Any] = {}
    for field in config.SCHEMA_FIELDS:
        value = values.get(field)
        if field in {"repository_urls", "labels", "secondary_labels", "tasks", "methods"}:
            record[field] = clean_list(value)
        else:
            record[field] = clean_text(value)
    if not record["repository_url"] and record["repository_urls"]:
        record["repository_url"] = record["repository_urls"][0]
    if record["repository_url"] and record["repository_url"] not in record["repository_urls"]:
        record["repository_urls"] = [record["repository_url"], *record["repository_urls"]]
    return record


def coverage_counts(records: Iterable[dict[str, Any]]) -> dict[str, int]:
    """Compute common dataset coverage counters without adding flags to records."""
    rows = list(records)
    return {
        "total": len(rows),
        "with_repository": sum(bool(row.get("repository_url")) for row in rows),
        "with_labels": sum(bool(row.get("labels")) for row in rows),
        "single_label": sum(len(row.get("labels") or []) == 1 for row in rows),
        "multi_label": sum(len(row.get("labels") or []) > 1 for row in rows),
        "with_publication_metadata": sum(bool(row.get("paper_title") or row.get("paper_abstract")) for row in rows),
    }


def merge_enrichment(record: dict[str, Any], github: dict[str, Any] | None, somef: dict[str, Any] | None) -> dict[str, Any]:
    """Attach simplified GitHub and SoMEF metadata to an aligned record."""
    merged = dict(record)
    github = github or {}
    somef = somef or {}
    merged.update(
        {
            "repository_url_normalized": github.get("repository_url_normalized"),
            "repository_title": github.get("repository_title"),
            "repository_description": github.get("repository_description"),
            "repository_keywords": github.get("repository_keywords") or [],
            "readme_content": github.get("readme_content"),
            "github_default_branch": github.get("default_branch"),
            "github_license": github.get("license"),
            "github_error": github.get("error"),
            "somef_description": somef.get("somef_description"),
            "somef_citation": somef.get("citation"),
            "somef_title": somef.get("title"),
            "somef_keywords": somef.get("keywords") or [],
        }
    )
    return merged


def labels_without_exclusions(record: dict[str, Any]) -> list[str]:
    """Return labels after removing source-specific non-informative classes."""
    labels = clean_list(record.get("labels"))
    excluded = config.EXCLUDED_LABELS_BY_SOURCE.get(record.get("source"), set())
    return [label for label in labels if label not in excluded]


def final_record(record: dict[str, Any], label_mode: str) -> dict[str, Any] | None:
    """Build a final ML-ready record for ``single`` or ``multi`` label mode."""
    labels = labels_without_exclusions(record)
    if label_mode == "single":
        if len(labels) != 1:
            return None
        label: str | list[str] = labels[0]
    elif label_mode == "multi":
        if not labels:
            return None
        label = labels
    else:
        raise ValueError(f"Unknown label mode: {label_mode}")

    output = {
        "source": record.get("source"),
        "item_id": record.get("item_id"),
        "doi": record.get("doi"),
        "publication_url": record.get("publication_url"),
        "repository_url": record.get("repository_url"),
        "repository_urls": record.get("repository_urls") or [],
        "repository_url_normalized": record.get("repository_url_normalized"),
        "label": label,
    }
    for field in config.TEXT_ATTRIBUTES:
        output[field] = labels if field == "labels" else record.get(field)
    output["paper_title"] = clean_markup_text(output.get("paper_title"))
    output["paper_abstract"] = clean_markup_text(output.get("paper_abstract"))
    output["software_description"] = clean_markup_text(output.get("software_description"))
    output["repository_description"] = clean_markup_text(output.get("repository_description"))
    output["somef_description"] = clean_markup_text(output.get("somef_description"))
    return output
