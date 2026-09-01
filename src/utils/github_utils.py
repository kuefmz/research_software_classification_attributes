"""GitHub repository normalization, API fetching, and cache helpers."""
from __future__ import annotations

import base64
import logging
import os
import re
import time
from typing import Any
from urllib.parse import urlparse

import requests

from src import config

LOGGER = logging.getLogger(__name__)
GITHUB_RE = re.compile(r"github\.com[:/]([^/\s]+)/([^/#?\s]+)", re.IGNORECASE)


def normalize_github_url(url: str | None) -> str | None:
    """Normalize GitHub repository URLs to ``https://github.com/owner/repo``."""
    if not url:
        return None
    match = GITHUB_RE.search(str(url).strip())
    if not match:
        return None
    owner = match.group(1).strip()
    repo = match.group(2).strip().removesuffix(".git")
    if not owner or not repo:
        return None
    return f"https://github.com/{owner}/{repo}"


def owner_repo(normalized_url: str) -> tuple[str, str]:
    """Return owner and repository name from a normalized GitHub URL."""
    parsed = urlparse(normalized_url)
    parts = [part for part in parsed.path.split("/") if part]
    if len(parts) < 2:
        raise ValueError(f"Not a repository URL: {normalized_url}")
    return parts[0], parts[1]


def raw_readme_candidate_urls(repository_url: str) -> list[str]:
    """Return non-API raw README URL candidates for a GitHub repository."""
    owner, repo = owner_repo(repository_url)
    filenames = ["README.md", "readme.md", "Readme.md", "README.rst", "README.txt", "README"]
    refs = ["HEAD", "main", "master"]
    urls: list[str] = []
    for ref in refs:
        for filename in filenames:
            urls.append(f"https://raw.githubusercontent.com/{owner}/{repo}/{ref}/{filename}")
    return urls


def fetch_readme_without_api(repository_url: str, session: requests.Session | None = None) -> tuple[str | None, dict[str, Any]]:
    """Fetch README content through raw GitHub URLs without using the GitHub API."""
    normalized = normalize_github_url(repository_url)
    if not normalized:
        return None, {"error": "not_github_url", "repository_url": repository_url}

    owns_session = session is None
    if session is None:
        session = requests.Session()
    try:
        attempts = []
        for url in raw_readme_candidate_urls(normalized):
            try:
                response = session.get(url, timeout=config.GITHUB_REQUEST_TIMEOUT, headers={"User-Agent": config.GITHUB_USER_AGENT})
                attempts.append({"url": url, "status_code": response.status_code})
                if response.status_code == 200 and response.text.strip():
                    return response.text, {"source_url": url, "attempts": attempts, "error": None}
            except requests.RequestException as exc:
                attempts.append({"url": url, "error": str(exc)})
        return None, {"error": "readme_not_found", "attempts": attempts}
    finally:
        if owns_session:
            session.close()


def github_headers() -> dict[str, str]:
    """Build API headers, using ``GITHUB_TOKEN`` when present."""
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": config.GITHUB_USER_AGENT,
        "X-GitHub-Api-Version": "2022-11-28",
    }
    token = os.environ.get(config.GITHUB_TOKEN_ENV_VAR)
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def log_rate_limit(response: requests.Response) -> None:
    """Log GitHub rate-limit headers when available."""
    remaining = response.headers.get("X-RateLimit-Remaining")
    reset = response.headers.get("X-RateLimit-Reset")
    if remaining is not None:
        LOGGER.info("GitHub rate limit remaining=%s reset=%s", remaining, reset)


def _get_json(session: requests.Session, url: str) -> tuple[dict[str, Any] | list[Any] | None, str | None]:
    try:
        response = session.get(url, timeout=config.GITHUB_REQUEST_TIMEOUT)
        log_rate_limit(response)
        if response.status_code == 404:
            return None, "not_found"
        if response.status_code == 403 and response.headers.get("X-RateLimit-Remaining") == "0":
            LOGGER.warning("GitHub rate limit exhausted while fetching %s", url)
            time.sleep(config.GITHUB_RATE_LIMIT_SLEEP_SECONDS)
        response.raise_for_status()
        return response.json(), None
    except requests.RequestException as exc:
        return None, str(exc)


def fetch_repository_metadata(repository_url: str, session: requests.Session | None = None) -> dict[str, Any]:
    """Fetch repository metadata and README content from the GitHub API."""
    normalized = normalize_github_url(repository_url)
    if not normalized:
        return {"repository_url": repository_url, "repository_url_normalized": None, "error": "not_github_url"}

    owns_session = session is None
    if session is None:
        session = requests.Session()
        session.headers.update(github_headers())

    try:
        owner, repo = owner_repo(normalized)
        api_repo = f"{config.GITHUB_API_BASE}/repos/{owner}/{repo}"
        repo_payload, repo_error = _get_json(session, api_repo)
        if repo_error:
            return {"repository_url": repository_url, "repository_url_normalized": normalized, "error": repo_error}

        assert isinstance(repo_payload, dict)
        readme_content = None
        readme_payload, readme_error = _get_json(session, f"{api_repo}/readme")
        if isinstance(readme_payload, dict) and readme_payload.get("content"):
            try:
                readme_content = base64.b64decode(readme_payload["content"]).decode("utf-8", errors="replace")
            except (ValueError, TypeError) as exc:
                readme_error = f"readme_decode_error: {exc}"

        topics = repo_payload.get("topics") or []
        license_info = repo_payload.get("license") or {}
        return {
            "repository_url": repository_url,
            "repository_url_normalized": normalized,
            "repository_title": repo_payload.get("name") or repo,
            "repository_full_name": repo_payload.get("full_name"),
            "repository_description": repo_payload.get("description"),
            "repository_keywords": topics,
            "readme_content": readme_content,
            "default_branch": repo_payload.get("default_branch"),
            "license": license_info.get("spdx_id") or license_info.get("name"),
            "html_url": repo_payload.get("html_url"),
            "error": readme_error,
        }
    finally:
        if owns_session:
            session.close()
