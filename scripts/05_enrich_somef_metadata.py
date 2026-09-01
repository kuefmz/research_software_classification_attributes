#!/usr/bin/env python3
"""Collect README files, run SoMEF on them, and write enriched datasets.

This script is artifact-first and cache-first:

* each repository gets a folder under
  ``data/intermediate/github_enrichment/repository_artifacts/``;
* the README is saved as ``README.md`` in that folder;
* raw SoMEF output is saved as ``somef.json`` in that same folder;
* existing README and SoMEF files are reused, so interrupted runs can resume
  without refetching or rerunning completed repositories.

README fetching uses raw GitHub URLs such as
``https://raw.githubusercontent.com/<owner>/<repo>/HEAD/README.md`` and does not
use the GitHub API. SoMEF is run on the saved README with ``somef describe -d``.
"""
from __future__ import annotations

import json
import logging
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path

import requests

try:
    from tqdm import tqdm
except ImportError:  # pragma: no cover
    def tqdm(iterable, **_: object):
        return iterable

sys.path.append(str(Path(__file__).resolve().parent.parent))

from src import config
from src.utils.github_utils import fetch_readme_without_api, normalize_github_url, owner_repo
from src.utils.io_utils import configure_logging, read_jsonl, write_jsonl
from src.utils.somef_utils import repository_slug, run_somef_for_readme, simplify_somef_result, somef_command

LOGGER = logging.getLogger("enrich_somef_metadata")

INPUT_DATASETS = {
    config.PWC_SINGLE_LABEL_JSONL: config.PWC_SINGLE_LABEL_WITH_SOMEF_JSONL,
    config.PWC_MULTI_LABEL_JSONL: config.PWC_MULTI_LABEL_WITH_SOMEF_JSONL,
    config.BIOTOOLS_SINGLE_LABEL_JSONL: config.BIOTOOLS_SINGLE_LABEL_WITH_SOMEF_JSONL,
    config.BIOTOOLS_MULTI_LABEL_JSONL: config.BIOTOOLS_MULTI_LABEL_WITH_SOMEF_JSONL,
    config.COMBINED_ALL_JSONL: config.SOMEF_DATASET_JSONL,
}


def _check_somef_available() -> None:
    """Fail early with a useful message if the SoMEF CLI is not installed."""
    try:
        subprocess.run([*somef_command(), "--help"], check=True, capture_output=True, text=True)
    except (OSError, subprocess.CalledProcessError) as exc:
        raise RuntimeError(
            "SoMEF CLI is not available. Install it and run `somef configure` before this script."
        ) from exc


def _configure_file_logging() -> None:
    """Add a detailed file log for long SoMEF runs."""
    config.SOMEF_RUN_LOG.parent.mkdir(parents=True, exist_ok=True)
    root_logger = logging.getLogger()
    log_path = str(config.SOMEF_RUN_LOG)
    if any(isinstance(handler, logging.FileHandler) and handler.baseFilename == log_path for handler in root_logger.handlers):
        return
    handler = logging.FileHandler(config.SOMEF_RUN_LOG, encoding="utf-8")
    handler.setLevel(logging.INFO)
    handler.setFormatter(
        logging.Formatter(
            "%(asctime)s %(levelname)s %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )
    root_logger.addHandler(handler)


def _load_all_base_records() -> list[dict]:
    """Load combined final records to identify unique repositories."""
    if not config.COMBINED_ALL_JSONL.exists():
        raise FileNotFoundError(f"Run scripts/00_run_data_preparation.py first: {config.COMBINED_ALL_JSONL}")
    return list(read_jsonl(config.COMBINED_ALL_JSONL))


def _artifact_dir(repository_url: str) -> Path:
    """Return the per-repository artifact directory."""
    return config.REPOSITORY_ARTIFACTS_DIR / repository_slug(repository_url)


def _readme_path(repository_url: str) -> Path:
    """Return the saved README path for a repository."""
    return _artifact_dir(repository_url) / "README.md"


def _somef_json_path(repository_url: str) -> Path:
    """Return the raw SoMEF JSON path for a repository."""
    return _artifact_dir(repository_url) / "somef.json"


def _repo_metadata_path(repository_url: str) -> Path:
    """Return the small local metadata path for README fetch provenance."""
    return _artifact_dir(repository_url) / "metadata.json"


def _write_json(path: Path, payload: dict) -> None:
    """Write one JSON file, creating parents first."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")


def _repository_title(repository_url: str) -> str | None:
    """Return a simple repository title from owner/repo when available."""
    try:
        _, repo = owner_repo(repository_url)
        return repo
    except ValueError:
        return None


def _ensure_readme(repo: str, session: requests.Session) -> dict:
    """Ensure one repository has a saved README artifact."""
    readme_path = _readme_path(repo)
    if readme_path.exists():
        result = {
            "repository_url": repo,
            "artifact_dir": str(_artifact_dir(repo)),
            "readme_path": str(readme_path),
            "status": "skipped_existing_readme",
            "seconds_without_sleep": 0.0,
        }
        LOGGER.info("README item repo=%s status=%s seconds_without_sleep=0.000", repo, result["status"])
        return result

    started = time.time()
    readme_path.parent.mkdir(parents=True, exist_ok=True)
    readme_content, metadata = fetch_readme_without_api(repo, session=session)
    metadata.update(
        {
            "repository_url": repo,
            "repository_title": _repository_title(repo),
            "artifact_dir": str(_artifact_dir(repo)),
            "readme_path": str(readme_path),
        }
    )
    if readme_content:
        readme_path.write_text(readme_content, encoding="utf-8")
        status = "saved_readme"
    else:
        status = "readme_not_found"
    _write_json(_repo_metadata_path(repo), metadata)
    elapsed = round(time.time() - started, 3)
    result = {
        "repository_url": repo,
        "artifact_dir": str(_artifact_dir(repo)),
        "readme_path": str(readme_path) if readme_path.exists() else None,
        "status": status,
        "seconds_without_sleep": elapsed,
    }
    LOGGER.info("README item repo=%s status=%s seconds_without_sleep=%.3f", repo, status, elapsed)
    time.sleep(config.README_FETCH_SLEEP_SECONDS)
    return result


def _ensure_somef(repo: str) -> dict:
    """Ensure one repository has a saved SoMEF JSON artifact."""
    somef_path = _somef_json_path(repo)
    if somef_path.exists():
        result = {
            "repository_url": repo,
            "artifact_dir": str(_artifact_dir(repo)),
            "somef_json_path": str(somef_path),
            "status": "skipped_existing_somef_json",
            "seconds_without_sleep": 0.0,
        }
        LOGGER.info("SoMEF item repo=%s status=%s seconds_without_sleep=0.000", repo, result["status"])
        return result
    if not _readme_path(repo).exists():
        result = {
            "repository_url": repo,
            "artifact_dir": str(_artifact_dir(repo)),
            "somef_json_path": None,
            "status": "skipped_missing_readme",
            "seconds_without_sleep": 0.0,
        }
        LOGGER.info("SoMEF item repo=%s status=%s seconds_without_sleep=0.000", repo, result["status"])
        return result

    started = time.time()
    try:
        completed = run_somef_for_readme(_readme_path(repo).resolve(), somef_path.resolve(), threshold=config.SOMEF_THRESHOLD)
        status = "saved_somef_json"
        result = {
            "repository_url": repo,
            "artifact_dir": str(_artifact_dir(repo)),
            "readme_path": str(_readme_path(repo)),
            "somef_json_path": str(somef_path),
            "status": status,
            "seconds_without_sleep": round(time.time() - started, 3),
            "stdout_tail": completed.stdout[-500:] if completed.stdout else None,
            "stderr_tail": completed.stderr[-500:] if completed.stderr else None,
        }
    except (OSError, subprocess.CalledProcessError, RuntimeError) as exc:
        _write_json(
            somef_path,
            {
                "repository_url": repo,
                "readme_path": str(_readme_path(repo)),
                "error": str(exc),
                "stdout": getattr(exc, "stdout", None),
                "stderr": getattr(exc, "stderr", None),
            },
        )
        result = {
            "repository_url": repo,
            "artifact_dir": str(_artifact_dir(repo)),
            "readme_path": str(_readme_path(repo)),
            "somef_json_path": str(somef_path),
            "status": "error_json_written_exception",
            "seconds_without_sleep": round(time.time() - started, 3),
        }
        LOGGER.warning("SoMEF failed for %s; saved error JSON to %s", repo, somef_path)
    LOGGER.info(
        "SoMEF item repo=%s status=%s seconds_without_sleep=%.3f",
        repo,
        result["status"],
        result["seconds_without_sleep"],
    )
    time.sleep(config.SOMEF_SLEEP_SECONDS)
    return result


def _collect_repository_artifacts(repositories: list[str]) -> list[dict]:
    """Ensure README and SoMEF artifacts repository-by-repository."""
    manifest: list[dict] = []
    with requests.Session() as session:
        for repo in tqdm(repositories, desc="Collecting README and SoMEF artifacts"):
            readme_result = _ensure_readme(repo, session)
            manifest.append({"artifact_type": "readme", **readme_result})
            somef_result = _ensure_somef(repo)
            manifest.append({"artifact_type": "somef", **somef_result})
            if len(manifest) % 100 == 0:
                write_jsonl(manifest, config.SOMEF_RUN_MANIFEST_JSONL)
    return manifest


def _load_artifact_summaries(repositories: list[str]) -> dict[str, dict]:
    """Load README content and simplified SoMEF output for repositories."""
    summaries: dict[str, dict] = {}
    for repo in repositories:
        readme_path = _readme_path(repo)
        somef_path = _somef_json_path(repo)
        metadata_path = _repo_metadata_path(repo)

        readme_content = readme_path.read_text(encoding="utf-8", errors="replace") if readme_path.exists() else None
        metadata = {}
        if metadata_path.exists():
            try:
                metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                metadata = {}

        somef_summary: dict = {}
        if somef_path.exists():
            try:
                raw_somef = json.loads(somef_path.read_text(encoding="utf-8"))
                somef_summary = simplify_somef_result(raw_somef)
                somef_summary["somef_error"] = raw_somef.get("error") if isinstance(raw_somef, dict) else None
            except json.JSONDecodeError as exc:
                somef_summary = {"somef_error": f"invalid_json: {exc}"}

        summaries[repo] = {
            "artifact_dir": str(_artifact_dir(repo)),
            "readme_path": str(readme_path) if readme_path.exists() else None,
            "readme_content": readme_content,
            "repository_title": somef_summary.get("title") or metadata.get("repository_title") or _repository_title(repo),
            "somef_json_path": str(somef_path) if somef_path.exists() else None,
            "somef_description": somef_summary.get("somef_description"),
            "somef_keywords": somef_summary.get("keywords") or [],
            "somef_title": somef_summary.get("title"),
            "somef_citation": somef_summary.get("citation"),
            "somef_error": somef_summary.get("somef_error"),
        }
    return summaries


def _merge_artifacts_into_dataset(input_path: Path, output_path: Path, summaries: dict[str, dict]) -> None:
    """Write one dataset copy with saved README and simplified SoMEF metadata."""
    records = []
    for record in read_jsonl(input_path):
        normalized = normalize_github_url(record.get("repository_url"))
        summary = summaries.get(normalized, {}) if normalized else {}
        row = dict(record)
        row["repository_url_normalized"] = normalized
        row["repository_title"] = summary.get("repository_title")
        row["readme_content"] = summary.get("readme_content")
        row["readme_path"] = summary.get("readme_path")
        row["repository_artifact_dir"] = summary.get("artifact_dir")
        row["somef_description"] = summary.get("somef_description")
        row["somef_keywords"] = summary.get("somef_keywords") or []
        row["somef_title"] = summary.get("somef_title")
        row["somef_citation"] = summary.get("somef_citation")
        row["somef_json_path"] = summary.get("somef_json_path")
        row["somef_error"] = summary.get("somef_error")
        records.append(row)
    write_jsonl(records, output_path)
    LOGGER.info(
        "Wrote README+SoMEF dataset: %s rows=%s with_readme=%s with_somef_json=%s",
        output_path,
        f"{len(records):,}",
        f"{sum(bool(record.get('readme_content')) for record in records):,}",
        f"{sum(bool(record.get('somef_json_path')) for record in records):,}",
    )


def main() -> None:
    configure_logging()
    _configure_file_logging()
    config.ensure_directories()
    _check_somef_available()
    LOGGER.info("Detailed run log: %s", config.SOMEF_RUN_LOG)

    base_records = _load_all_base_records()
    repositories = sorted(
        {
            normalized
            for normalized in (normalize_github_url(record.get("repository_url")) for record in base_records)
            if normalized
        }
    )

    manifest = _collect_repository_artifacts(repositories)
    write_jsonl(manifest, config.SOMEF_RUN_MANIFEST_JSONL)
    status_counts = Counter(f"{row.get('artifact_type')}:{row.get('status')}" for row in manifest)
    LOGGER.info("Artifact status counts: %s", dict(sorted(status_counts.items())))
    LOGGER.info("Wrote artifact manifest: %s", config.SOMEF_RUN_MANIFEST_JSONL)

    summaries = _load_artifact_summaries(repositories)
    for input_path, output_path in INPUT_DATASETS.items():
        if input_path.exists():
            _merge_artifacts_into_dataset(input_path, output_path, summaries)
        else:
            LOGGER.warning("Skipping missing input dataset: %s", input_path)


if __name__ == "__main__":
    main()
