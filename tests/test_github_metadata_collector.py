from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts import collect_github_repository_metadata as collector


class GitHubMetadataCollectorTest(unittest.TestCase):
    def test_github_url_normalization_and_owner_repo_extraction(self):
        self.assertEqual(
            collector.normalize_github_url("git@github.com:Owner/Repo.git"),
            "https://github.com/Owner/Repo",
        )
        self.assertEqual(
            collector.normalize_github_url("https://github.com/Owner/Repo.git/?tab=readme#x"),
            "https://github.com/Owner/Repo",
        )
        self.assertEqual(collector.owner_repo("https://github.com/Owner/Repo"), ("Owner", "Repo"))

    def test_discovery_deduplicates_repositories_and_counts_invalid_urls(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            first = root / "one"
            second = root / "two"
            bad = root / "bad"
            first.mkdir()
            second.mkdir()
            bad.mkdir()
            (first / "metadata.json").write_text(
                json.dumps({"repository_url": "https://github.com/Owner/Repo"}),
                encoding="utf-8",
            )
            (second / "metadata.json").write_text(
                json.dumps({"repository_url": "https://github.com/Owner/Repo.git"}),
                encoding="utf-8",
            )
            (bad / "metadata.json").write_text(
                json.dumps({"repository_url": "https://example.org/not-github"}),
                encoding="utf-8",
            )

            result = collector.discover_repositories(root)

        self.assertEqual(result.metadata_files_scanned, 3)
        self.assertEqual(result.valid_github_repositories_found, 2)
        self.assertEqual(result.unique_repositories, ["https://github.com/Owner/Repo"])
        self.assertEqual(result.invalid_unusable_urls, 1)

    def test_graphql_result_parsing_extracts_topics(self):
        repositories = ["https://github.com/Owner/Repo"]
        query, aliases = collector.build_graphql_query(repositories)
        self.assertIn("repositoryTopics(first: 100)", query)
        payload = {
            "data": {
                "repo0": {
                    "name": "Repo",
                    "nameWithOwner": "Owner/Repo",
                    "url": "https://github.com/Owner/Repo",
                    "description": "About text",
                    "repositoryTopics": {
                        "nodes": [
                            {"topic": {"name": "bioinformatics"}},
                            {"topic": {"name": "workflow"}},
                        ]
                    },
                }
            }
        }

        rows = collector.parse_graphql_response(repositories, aliases, payload, "2026-09-02T00:00:00Z")

        self.assertEqual(rows[0]["status"], "success")
        self.assertEqual(rows[0]["repository_title"], "Repo")
        self.assertEqual(rows[0]["repository_full_name"], "Owner/Repo")
        self.assertEqual(rows[0]["repository_description"], "About text")
        self.assertEqual(rows[0]["repository_keywords"], ["bioinformatics", "workflow"])

    def test_graphql_null_repository_is_retained_as_inaccessible(self):
        repositories = ["https://github.com/Owner/Missing"]
        _query, aliases = collector.build_graphql_query(repositories)
        payload = {"data": {"repo0": None}, "errors": [{"type": "NOT_FOUND"}]}

        rows = collector.parse_graphql_response(repositories, aliases, payload, "2026-09-02T00:00:00Z")

        self.assertEqual(rows[0]["status"], "not_found_or_inaccessible")
        self.assertEqual(rows[0]["repository_url_requested"], "https://github.com/Owner/Missing")

    def test_resume_skips_terminal_rows_but_retries_temporary_errors(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            output = Path(tmp_dir) / "snapshot.jsonl"
            rows = [
                {"repository_url_requested": "https://github.com/Owner/Done", "status": "success"},
                {"repository_url_requested": "https://github.com/Owner/Missing", "status": "not_found_or_inaccessible"},
                {"repository_url_requested": "https://github.com/Owner/Retry", "status": "http_429"},
            ]
            output.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")

            completed = collector.completed_urls_from_output(output)

        self.assertEqual(
            completed,
            {"https://github.com/Owner/Done", "https://github.com/Owner/Missing"},
        )

    def test_fetch_batch_uses_mocked_api_response(self):
        payload = {
            "data": {
                "repo0": {
                    "name": "Repo",
                    "nameWithOwner": "Owner/Repo",
                    "url": "https://github.com/Owner/Repo",
                    "description": None,
                    "repositoryTopics": {"nodes": [{"topic": {"name": "topic-a"}}]},
                }
            }
        }
        with mock.patch.object(collector, "github_graphql_request", return_value=(200, {}, payload)) as request:
            rows = collector.fetch_batch(["https://github.com/Owner/Repo"], "token")

        request.assert_called_once()
        self.assertEqual(rows[0]["status"], "success")
        self.assertEqual(rows[0]["repository_keywords"], ["topic-a"])


if __name__ == "__main__":
    unittest.main()
