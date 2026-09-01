"""Small wrapper around SoMEF extraction for README content.

SoMEF is optional because it has heavier dependencies than the alignment code.
When installed, this module first tries the documented Python API. If the API is
not available in the installed version, it falls back to the ``somef`` command.
"""
from __future__ import annotations

import json
import logging
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from src.utils.text_utils import clean_markup_text

LOGGER = logging.getLogger(__name__)


def _first_text(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value.strip() or None
    if isinstance(value, list):
        for item in value:
            text = _first_text(item)
            if text:
                return text
    if isinstance(value, dict):
        for key in ("excerpt", "result", "value", "text", "name"):
            text = _first_text(value.get(key))
            if text:
                return text
    return None


def _all_texts(value: Any) -> list[str]:
    """Collect short text leaves from nested SoMEF values."""
    if value is None:
        return []
    if isinstance(value, str):
        text = value.strip()
        return [text] if text else []
    if isinstance(value, list):
        texts: list[str] = []
        for item in value:
            texts.extend(_all_texts(item))
        return texts
    if isinstance(value, dict):
        texts: list[str] = []
        for key in ("excerpt", "result", "value", "text", "name"):
            if key in value:
                texts.extend(_all_texts(value.get(key)))
        if texts:
            return texts
        for item in value.values():
            texts.extend(_all_texts(item))
        return texts
    return []


def _unique_clean_texts(value: Any) -> list[str]:
    cleaned: list[str] = []
    for text in _all_texts(value):
        normalized = clean_markup_text(text)
        if normalized and normalized not in cleaned:
            cleaned.append(normalized)
    return cleaned


def simplify_somef_result(result: dict[str, Any]) -> dict[str, Any]:
    """Extract fields needed by the ML datasets from raw SoMEF output."""
    return {
        "somef_description": clean_markup_text(_first_text(result.get("description"))),
        "citation": clean_markup_text(_first_text(result.get("citation"))),
        "title": clean_markup_text(_first_text(result.get("name") or result.get("title"))),
        "keywords": _unique_clean_texts(result.get("keywords") or result.get("keyword")),
        "raw_somef": result,
    }


def repository_slug(repository_url: str) -> str:
    """Create a stable filesystem-safe slug for a GitHub repository URL."""
    slug = re.sub(r"^https?://(?:www\.)?github\.com/", "", repository_url.rstrip("/"), flags=re.IGNORECASE)
    slug = slug.removesuffix(".git")
    return re.sub(r"[^A-Za-z0-9_.-]+", "__", slug)


def somef_command() -> list[str]:
    """Return the SoMEF CLI command available in the current environment."""
    executable = shutil.which("somef")
    if executable:
        return [executable]
    return ["somef"]


def run_somef_for_repository(repository_url: str, output_path: Path, threshold: float = 0.8) -> subprocess.CompletedProcess[str]:
    """Run the documented SoMEF CLI against a GitHub repository URL.

    The caller validates that ``output_path`` was actually created, because some
    SoMEF failures can still exit after logging and attempting to save output.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    return subprocess.run(
        [
            *somef_command(),
            "describe",
            "-r",
            repository_url,
            "-o",
            str(output_path),
            "-t",
            str(threshold),
            "-p",
        ],
        check=True,
        capture_output=True,
        text=True,
    )


def run_somef_for_readme(readme_path: Path, output_path: Path, threshold: float = 0.8) -> subprocess.CompletedProcess[str]:
    """Run the SoMEF CLI against a saved README file.

    SoMEF versions have used different option names for local documentation
    files. Try the documented long/short forms first, then a legacy fallback.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    attempts = []
    for input_flag in ["-d", "--doc_src", "-i"]:
        if output_path.exists():
            output_path.unlink()
        completed = subprocess.run(
            [
                *somef_command(),
                "describe",
                input_flag,
                str(readme_path),
                "-o",
                str(output_path),
                "-t",
                str(threshold),
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        attempts.append(
            {
                "input_flag": input_flag,
                "returncode": completed.returncode,
                "stdout": completed.stdout,
                "stderr": completed.stderr,
                "output_exists": output_path.exists(),
                "output_size": output_path.stat().st_size if output_path.exists() else 0,
            }
        )
        if completed.returncode == 0 and output_path.exists() and output_path.stat().st_size > 0:
            return completed
    raise RuntimeError(json.dumps({"error": "somef_readme_variants_failed", "attempts": attempts}, ensure_ascii=False))


def extract_somef_from_readme(readme_content: str | None) -> dict[str, Any]:
    """Run SoMEF over README text and return raw plus simplified metadata."""
    if not readme_content:
        return {"somef_description": None, "citation": None, "title": None, "keywords": [], "raw_somef": {}}

    try:
        from somef import cli  # type: ignore

        result = cli.run_cli(readme_content=readme_content, ignore_classifiers=True)
        if isinstance(result, str):
            result = json.loads(result)
        if isinstance(result, dict):
            return simplify_somef_result(result)
    except Exception as exc:
        LOGGER.info("SoMEF Python API was unavailable or failed; trying CLI. Details: %s", exc)

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        readme_path = tmp / "README.md"
        output_path = tmp / "somef.json"
        readme_path.write_text(readme_content, encoding="utf-8")
        try:
            subprocess.run(
                ["somef", "describe", "-d", str(readme_path), "-o", str(output_path), "-t", "0.8"],
                check=True,
                capture_output=True,
                text=True,
            )
            return simplify_somef_result(json.loads(output_path.read_text(encoding="utf-8")))
        except (OSError, subprocess.CalledProcessError, json.JSONDecodeError) as exc:
            LOGGER.warning("SoMEF extraction failed: %s", exc)
            return {
                "somef_description": None,
                "citation": None,
                "title": None,
                "keywords": [],
                "raw_somef": {},
                "error": str(exc),
            }
