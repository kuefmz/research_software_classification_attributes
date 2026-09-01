"""Text normalization and attribute-combination helpers."""
from __future__ import annotations

import hashlib
import html
import json
import re
from collections.abc import Iterable
from typing import Any

from src import config


def clean_text(value: Any) -> str | None:
    """Return normalized text or ``None`` for empty/null-like values."""
    if value is None:
        return None
    if isinstance(value, float) and str(value) == "nan":
        return None
    text = re.sub(r"\s+", " ", str(value)).strip()
    if not text or text.lower() in {"nan", "none", "null"}:
        return None
    return text


def clean_markup_text(value: Any) -> str | None:
    """Clean publication text scraped from public metadata APIs.

    Open scholarly APIs sometimes return titles or abstracts with lightweight
    HTML/XML tags, encoded entities, or Markdown links. This cleaner removes
    those artifacts while preserving the human-readable content.
    """
    text = clean_text(value)
    if not text:
        return None
    text = html.unescape(text)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"\{\\?[^{}\s]+ ([^{}]+)\}", r"\1", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text or None


def ensure_list(value: Any) -> list[Any]:
    """Coerce nested data, JSON strings, and separator-delimited strings to a list."""
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple) or isinstance(value, set):
        return list(value)
    if isinstance(value, str):
        text = value.strip()
        if not text or text.lower() in {"nan", "none", "null", "[]"}:
            return []
        if text[0:1] in {"[", "{"}:
            try:
                parsed = json.loads(text)
            except json.JSONDecodeError:
                parsed = None
            if isinstance(parsed, list):
                return parsed
            if parsed:
                return [parsed]
        if "|" in text:
            return [part.strip() for part in text.split("|") if part.strip()]
        return [text]
    return [value]


def clean_list(value: Any) -> list[str]:
    """Return a deterministic list of unique, non-empty strings."""
    cleaned: list[str] = []
    for item in ensure_list(value):
        if isinstance(item, dict):
            item = item.get("term") or item.get("name") or item.get("title") or item.get("label")
        text = clean_text(item)
        if text and text not in cleaned:
            cleaned.append(text)
    return cleaned


def stable_id(*parts: Any) -> str:
    """Create a deterministic short identifier from stable record attributes."""
    raw = "|".join(clean_text(part) or "" for part in parts)
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


def flatten_for_text(value: Any) -> str:
    """Convert nested metadata into text suitable for vectorizers or prompts."""
    if value is None:
        return ""
    if isinstance(value, str):
        return clean_text(value) or ""
    if isinstance(value, dict):
        return " ".join(flatten_for_text(v) for v in value.values()).strip()
    if isinstance(value, Iterable):
        return " ".join(flatten_for_text(v) for v in value).strip()
    return clean_text(value) or ""


def build_text(record: dict[str, Any], attribute_names: Iterable[str]) -> str:
    """Concatenate selected attributes into a single normalized text field."""
    parts = [flatten_for_text(record.get(name)) for name in attribute_names]
    return re.sub(r"\s+", " ", " ".join(part for part in parts if part)).strip()


def build_attribute_texts(record: dict[str, Any]) -> dict[str, str]:
    """Generate all configured attribute-combination texts for one record."""
    return {
        name: build_text(record, attributes)
        for name, attributes in config.ATTRIBUTE_COMBINATIONS.items()
    }
