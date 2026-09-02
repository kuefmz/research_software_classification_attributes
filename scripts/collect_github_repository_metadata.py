#!/usr/bin/env python3
"""Collect a resumable GitHub repository metadata snapshot.

This script reads local repository artifact metadata, queries only the official
GitHub GraphQL API, and appends a new JSONL snapshot. It never modifies the
existing repository artifact directories.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable, Mapping
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

sys.path.append(str(Path(__file__).resolve().parent.parent))

from src import config
from src.utils.github_utils import normalize_github_url, owner_repo
from src.utils.text_utils import clean_text


GRAPHQL_URL = "https://api.github.com/graphql"
DEFAULT_OUTPUT = config.GITHUB_ENRICHMENT_DIR / "github_metadata_snapshot_2026-09-02.jsonl"
DEFAULT_SUMMARY = config.GITHUB_ENRICHMENT_DIR / "github_metadata_snapshot_2026-09-02_summary.json"
DEFAULT_BATCH_SIZE = 35
MAX_RETRIES = 5
RETRYABLE_STATUSES = {"api_error", "http_403", "http_429", "http_500", "http_502", "http_503", "http_504", "timeout"}
TERMINAL_STATUSES = {"success", "not_found_or_inaccessible", "invalid_url"}


@dataclass
class DiscoveryResult:
    metadata_files_scanned: int = 0
    valid_github_repositories_found: int = 0
    unique_repositories: list[str] = field(default_factory=list)
    invalid_unusable_urls: int = 0
    invalid_examples: list[str] = field(default_factory=list)


def utc_now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def metadata_paths(root: Path) -> Iterable[Path]:
    yield from sorted(root.glob("**/metadata.json"))


def load_json(path: Path) -> Mapping[str, Any] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def repository_url_from_metadata(metadata: Mapping[str, Any]) -> str | None:
    for field_name in ("repository_url", "repository_url_normalized", "html_url", "url"):
        value = clean_text(metadata.get(field_name))
        if normalize_github_url(value):
            return value
    attempts = metadata.get("attempts")
    if isinstance(attempts, list):
        for attempt in attempts:
            if isinstance(attempt, dict):
                value = clean_text(attempt.get("repository_url") or attempt.get("url"))
                if normalize_github_url(value):
                    return value
    return None


def discover_repositories(root: Path) -> DiscoveryResult:
    result = DiscoveryResult()
    seen: set[str] = set()
    for path in metadata_paths(root):
        result.metadata_files_scanned += 1
        metadata = load_json(path)
        raw_url = repository_url_from_metadata(metadata or {})
        normalized = normalize_github_url(raw_url)
        if not normalized:
            result.invalid_unusable_urls += 1
            if len(result.invalid_examples) < 10:
                result.invalid_examples.append(str(path))
            continue
        result.valid_github_repositories_found += 1
        if normalized not in seen:
            seen.add(normalized)
            result.unique_repositories.append(normalized)
    return result


def completed_urls_from_output(path: Path) -> set[str]:
    completed: set[str] = set()
    if not path.exists():
        return completed
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(row, dict):
                continue
            status = clean_text(row.get("status"))
            if status not in TERMINAL_STATUSES:
                continue
            requested = normalize_github_url(row.get("repository_url_requested") or row.get("repository_url"))
            if requested:
                completed.add(requested)
    return completed


def batched(values: list[str], size: int) -> Iterable[list[str]]:
    for index in range(0, len(values), size):
        yield values[index : index + size]


def graphql_alias(index: int) -> str:
    return f"repo{index}"


def build_graphql_query(repositories: list[str]) -> tuple[str, dict[str, tuple[str, str, str]]]:
    aliases: dict[str, tuple[str, str, str]] = {}
    lines = ["query {"]
    for index, repository_url in enumerate(repositories):
        owner, repo = owner_repo(repository_url)
        alias = graphql_alias(index)
        aliases[alias] = (repository_url, owner, repo)
        lines.extend(
            [
                f'  {alias}: repository(owner: {json.dumps(owner)}, name: {json.dumps(repo)}) {{',
                "    name",
                "    nameWithOwner",
                "    url",
                "    description",
                "    repositoryTopics(first: 100) {",
                "      nodes {",
                "        topic {",
                "          name",
                "        }",
                "      }",
                "    }",
                "  }",
            ]
        )
    lines.append("}")
    return "\n".join(lines), aliases


def topics_from_repository(node: Mapping[str, Any] | None) -> list[str]:
    if not node:
        return []
    topics = node.get("repositoryTopics")
    nodes = topics.get("nodes") if isinstance(topics, dict) else []
    values: list[str] = []
    if isinstance(nodes, list):
        for item in nodes:
            if not isinstance(item, dict):
                continue
            topic = item.get("topic")
            name = clean_text(topic.get("name") if isinstance(topic, dict) else None)
            if name and name not in values:
                values.append(name)
    return values


def row_from_repository_node(
    requested_url: str,
    node: Mapping[str, Any] | None,
    retrieved_at: str,
) -> dict[str, Any]:
    if not node:
        return {
            "repository_url_requested": requested_url,
            "repository_url": requested_url,
            "repository_title": None,
            "repository_full_name": None,
            "repository_description": None,
            "repository_keywords": [],
            "retrieved_at": retrieved_at,
            "source": "GitHub GraphQL API",
            "status": "not_found_or_inaccessible",
        }

    repository_url = normalize_github_url(node.get("url")) or requested_url
    full_name = clean_text(node.get("nameWithOwner"))
    return {
        "repository_url_requested": requested_url,
        "repository_url": repository_url,
        "repository_title": clean_text(node.get("name")),
        "repository_full_name": full_name,
        "repository_description": clean_text(node.get("description")),
        "repository_keywords": topics_from_repository(node),
        "retrieved_at": retrieved_at,
        "source": "GitHub GraphQL API",
        "status": "success",
    }


def parse_graphql_response(
    repositories: list[str],
    aliases: Mapping[str, tuple[str, str, str]],
    payload: Mapping[str, Any],
    retrieved_at: str,
) -> list[dict[str, Any]]:
    data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
    rows = []
    for alias, (requested_url, _owner, _repo) in aliases.items():
        node = data.get(alias) if isinstance(data, dict) else None
        rows.append(row_from_repository_node(requested_url, node if isinstance(node, dict) else None, retrieved_at))
    requested = {value[0] for value in aliases.values()}
    for repository_url in repositories:
        if repository_url not in requested:
            rows.append(error_row(repository_url, "invalid_url", "Repository URL could not be included in query."))
    return rows


def error_row(repository_url: str, status: str, message: str) -> dict[str, Any]:
    return {
        "repository_url_requested": repository_url,
        "repository_url": repository_url,
        "repository_title": None,
        "repository_full_name": None,
        "repository_description": None,
        "repository_keywords": [],
        "retrieved_at": utc_now_iso(),
        "source": "GitHub GraphQL API",
        "status": status,
        "error": message,
    }


def token_from_environment() -> str | None:
    token = os.environ.get("GITHUB_TOKEN")
    return token.strip() if token and token.strip() else None


def token_from_gh() -> str | None:
    try:
        completed = subprocess.run(
            ["gh", "auth", "token"],
            check=False,
            capture_output=True,
            text=True,
            timeout=15,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    token = completed.stdout.strip()
    return token if completed.returncode == 0 and token else None


def get_token() -> str:
    token = token_from_environment() or token_from_gh()
    if not token:
        raise SystemExit("Authenticate using gh auth login or set GITHUB_TOKEN.")
    return token


def github_graphql_request(query: str, token: str, timeout: int = 60) -> tuple[int, dict[str, str], Mapping[str, Any]]:
    request = Request(
        GRAPHQL_URL,
        data=json.dumps({"query": query}).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "Content-Type": "application/json",
            "User-Agent": config.GITHUB_USER_AGENT,
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            body = response.read().decode("utf-8")
            payload = json.loads(body) if body else {}
            return response.status, dict(response.headers), payload
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        payload: Mapping[str, Any]
        try:
            payload = json.loads(body) if body else {}
        except json.JSONDecodeError:
            payload = {"message": body}
        return exc.code, dict(exc.headers), payload
    except TimeoutError as exc:
        raise RuntimeError("timeout") from exc
    except URLError as exc:
        reason = getattr(exc, "reason", exc)
        if isinstance(reason, TimeoutError):
            raise RuntimeError("timeout") from exc
        raise RuntimeError(str(reason)) from exc


def retry_delay(headers: Mapping[str, str], attempt: int) -> float:
    retry_after = headers.get("Retry-After") or headers.get("retry-after")
    if retry_after:
        try:
            return min(float(retry_after), 900.0)
        except ValueError:
            pass
    return min(2.0**attempt, 300.0)


def status_from_http(status_code: int, payload: Mapping[str, Any]) -> tuple[str, str]:
    message = clean_text(payload.get("message")) or f"HTTP {status_code}"
    if status_code == 200:
        errors = payload.get("errors")
        if isinstance(errors, list) and errors:
            error_text = json.dumps(errors, ensure_ascii=False)
            if "rate limit" in error_text.casefold() or "abuse" in error_text.casefold():
                return "api_error", error_text
            if not isinstance(payload.get("data"), dict):
                return "api_error", error_text
        return "success", ""
    if status_code in {403, 429, 500, 502, 503, 504}:
        return f"http_{status_code}", message
    return "api_error", message


def fetch_batch(repositories: list[str], token: str) -> list[dict[str, Any]]:
    query, aliases = build_graphql_query(repositories)
    last_status = "api_error"
    last_message = "request failed"
    for attempt in range(MAX_RETRIES):
        headers: Mapping[str, str] = {}
        try:
            status_code, headers, payload = github_graphql_request(query, token)
            status, message = status_from_http(status_code, payload)
            if status == "success":
                return parse_graphql_response(repositories, aliases, payload, utc_now_iso())
            last_status, last_message = status, message
        except RuntimeError as exc:
            last_status, last_message = "timeout", str(exc)
        if last_status not in RETRYABLE_STATUSES or attempt == MAX_RETRIES - 1:
            break
        time.sleep(retry_delay(headers, attempt))
    return [error_row(repository_url, last_status, last_message) for repository_url in repositories]


def append_rows(path: Path, rows: list[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def summary_from_output(
    output_path: Path,
    summary_path: Path,
    started_at: str,
    total_repositories: int,
    script_args: Mapping[str, Any],
) -> dict[str, Any]:
    rows = []
    if output_path.exists():
        with output_path.open("r", encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(row, dict):
                    rows.append(row)
    successes = [row for row in rows if row.get("status") == "success"]
    inaccessible = [row for row in rows if row.get("status") == "not_found_or_inaccessible"]
    with_description = [row for row in successes if clean_text(row.get("repository_description"))]
    with_topics = [row for row in successes if row.get("repository_keywords")]
    neither = [
        row
        for row in successes
        if not clean_text(row.get("repository_description")) and not row.get("repository_keywords")
    ]
    return {
        "retrieval_started_at": started_at,
        "summary_updated_at": utc_now_iso(),
        "total_repositories_discovered": total_repositories,
        "rows_written": len(rows),
        "successes": len(successes),
        "not_found_or_inaccessible": len(inaccessible),
        "repositories_with_description": len(with_description),
        "repositories_with_topics": len(with_topics),
        "repositories_with_neither": len(neither),
        "output_file_path": str(output_path),
        "summary_file_path": str(summary_path),
        "source": "GitHub GraphQL API",
        "script": "scripts/collect_github_repository_metadata.py",
        "script_version": "2026-09-02.1",
        "statuses": {
            "success": "Repository metadata was returned by GitHub GraphQL.",
            "not_found_or_inaccessible": "Repository was missing, deleted, private, or otherwise inaccessible to the token.",
            "invalid_url": "Local metadata did not yield a usable GitHub repository URL.",
            "api_error": "GitHub returned GraphQL or non-retryable API errors.",
            "http_403": "GitHub returned HTTP 403, including possible primary or secondary rate limits.",
            "http_429": "GitHub returned HTTP 429 rate limiting.",
            "http_5xx": "GitHub returned a transient server error; exact status is recorded per row.",
            "timeout": "The request timed out after bounded retries.",
        },
        "script_args": dict(script_args),
    }


def write_summary(summary_path: Path, summary: Mapping[str, Any]) -> None:
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = summary_path.with_suffix(summary_path.suffix + ".tmp")
    tmp_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp_path.replace(summary_path)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact-root", type=Path, default=config.REPOSITORY_ARTIFACTS_DIR)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--summary", type=Path, default=DEFAULT_SUMMARY)
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.batch_size < 1 or args.batch_size > 100:
        raise SystemExit("--batch-size must be between 1 and 100.")

    started_at = utc_now_iso()
    discovery = discover_repositories(args.artifact_root)
    repositories = list(discovery.unique_repositories)
    if args.limit is not None:
        repositories = repositories[: max(args.limit, 0)]

    completed = completed_urls_from_output(args.output)
    completed_for_run = {repository for repository in repositories if repository in completed}
    remaining = [repository for repository in repositories if repository not in completed]

    print(f"metadata files scanned: {discovery.metadata_files_scanned}")
    print(f"valid GitHub repositories found: {discovery.valid_github_repositories_found}")
    print(f"unique repositories: {len(discovery.unique_repositories)}")
    print(f"invalid/unusable URLs: {discovery.invalid_unusable_urls}")
    print(f"already completed in output: {len(completed_for_run)}")
    print(f"repositories remaining for this run: {len(remaining)}")

    if args.dry_run:
        return 0

    token = get_token()
    processed = len(completed_for_run)
    total = len(repositories)
    for batch in batched(remaining, args.batch_size):
        rows = fetch_batch(batch, token)
        append_rows(args.output, rows)
        processed += len(batch)
        summary = summary_from_output(
            args.output,
            args.summary,
            started_at,
            len(discovery.unique_repositories),
            {
                "artifact_root": str(args.artifact_root),
                "batch_size": args.batch_size,
                "limit": args.limit,
            },
        )
        write_summary(args.summary, summary)
        print(f"{processed} / {total} repositories processed")

    final_summary = summary_from_output(
        args.output,
        args.summary,
        started_at,
        len(discovery.unique_repositories),
        {
            "artifact_root": str(args.artifact_root),
            "batch_size": args.batch_size,
            "limit": args.limit,
        },
    )
    write_summary(args.summary, final_summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
