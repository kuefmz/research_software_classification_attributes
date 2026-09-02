from __future__ import annotations

import tempfile
import unittest
from collections import Counter
from pathlib import Path

from src.final_dataset_builder import (
    ArtifactLoader,
    BuildAudit,
    build_edam_mapping_rows,
    candidate_biotools_records,
    candidate_pwc_record,
    deterministic_id,
    duplicate_rows,
    edam_map_labels,
    edam_top_level_mappings,
    label_stats_rows,
    load_github_metadata_cache,
    missing_reason,
    parse_edam_ontology,
    pipeline_stage_rows,
    retention_reason,
    target_leakage_rows,
    update_level_view,
    update_record_audits,
    view_record,
)
from src.utils.github_utils import normalize_github_url
from src.utils.publication_utils import normalize_doi


EDAM_FIXTURE = """<?xml version="1.0"?>
<rdf:RDF
  xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"
  xmlns:owl="http://www.w3.org/2002/07/owl#"
  xmlns:rdfs="http://www.w3.org/2000/01/rdf-schema#">
  <owl:Ontology rdf:about="http://edamontology.org/EDAM.owl">
    <owl:versionInfo>fixture-edam</owl:versionInfo>
  </owl:Ontology>
  <owl:Class rdf:about="http://edamontology.org/topic_0003">
    <rdfs:label>Topic</rdfs:label>
  </owl:Class>
  <owl:Class rdf:about="http://edamontology.org/topic_1000">
    <rdfs:label>Biology</rdfs:label>
    <rdfs:subClassOf rdf:resource="http://edamontology.org/topic_0003"/>
  </owl:Class>
  <owl:Class rdf:about="http://edamontology.org/topic_2000">
    <rdfs:label>Informatics</rdfs:label>
    <rdfs:subClassOf rdf:resource="http://edamontology.org/topic_0003"/>
  </owl:Class>
  <owl:Class rdf:about="http://edamontology.org/topic_3000">
    <rdfs:label>Sequence analysis</rdfs:label>
    <rdfs:subClassOf rdf:resource="http://edamontology.org/topic_1000"/>
    <rdfs:subClassOf rdf:resource="http://edamontology.org/topic_2000"/>
  </owl:Class>
</rdf:RDF>
"""


class FinalDatasetBuilderTest(unittest.TestCase):
    def ontology(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        path = Path(tmp.name) / "EDAM.owl"
        path.write_text(EDAM_FIXTURE, encoding="utf-8")
        return parse_edam_ontology(path)

    def artifact_loader(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        return ArtifactLoader(Path(tmp.name), BuildAudit())

    def test_identifier_normalization_and_determinism(self):
        self.assertEqual(normalize_doi("https://doi.org/10.1234/ABC."), "10.1234/abc")
        self.assertEqual(
            normalize_github_url("git@github.com:Owner/Repo.git"),
            "https://github.com/Owner/Repo",
        )
        self.assertEqual(deterministic_id("a", "b"), deterministic_id("a", "b"))
        self.assertNotEqual(deterministic_id("a", "b"), deterministic_id("b", "a"))

    def test_edam_mapping_preserves_multi_parent_cases(self):
        ontology = self.ontology()
        mappings = edam_top_level_mappings("topic_3000", ontology)
        high_topics = {row["high_level_topic"] for row in mappings}
        self.assertEqual(high_topics, {"topic_1000", "topic_2000"})
        rows = build_edam_mapping_rows(ontology)
        labels, uris, statuses = edam_map_labels(
            ["Sequence analysis"],
            ["http://edamontology.org/topic_3000"],
            ontology,
            {"topic_3000": [row for row in rows if row["detailed_topic_id"] == "topic_3000"]},
        )
        self.assertEqual(set(labels), {"Biology", "Informatics"})
        self.assertIn("mapped", statuses)

    def test_generic_edam_topic_is_excluded(self):
        ontology = self.ontology()
        mappings = edam_top_level_mappings("topic_0003", ontology)
        self.assertEqual(mappings[0]["mapping_status"], "excluded_generic_or_admin_topic")
        self.assertIsNone(mappings[0]["high_level_topic"])

    def test_pwc_parsing_and_generic_high_level_exclusion(self):
        record = candidate_pwc_record(
            {
                "paper_url": "https://paperswithcode.com/paper/example",
                "url_abs": "https://arxiv.org/abs/1234.5678",
                "github_repo": "https://github.com/example/project",
                "main_collection_areas": ["General", "Natural Language Processing"],
                "papers with code categories": {"tasks": ["Question Answering"]},
                "paper_title": "Example Paper",
            },
            self.artifact_loader(),
        )
        self.assertEqual(record["high_level_labels"], ["Natural Language Processing"])
        self.assertIn("General", record["raw_source_labels"])
        self.assertEqual(record["fine_grained_labels"], ["Question Answering"])
        self.assertEqual(retention_reason(record), "retained")

    def test_biotools_expansion_and_edam_mapping(self):
        ontology = self.ontology()
        rows = build_edam_mapping_rows(ontology)
        lookup = {"topic_3000": [row for row in rows if row["detailed_topic_id"] == "topic_3000"]}
        records = candidate_biotools_records(
            {
                "biotools_id": "tool-a",
                "name": "Tool A",
                "description": "A tool",
                "github_url": "https://github.com/example/tool-a",
                "topic_terms": "Sequence analysis",
                "topic_uris": "http://edamontology.org/topic_3000",
                "doi": "10.1234/abc|10.5678/def",
            },
            {"biotoolsID": "tool-a", "function": []},
            ontology,
            lookup,
            {"10.1234/abc": {"paper_title": "Publication A", "metadata_error": None}},
            self.artifact_loader(),
        )
        self.assertEqual(len(records), 2)
        self.assertEqual(records[0]["paper_title"], "Publication A")
        self.assertEqual(set(records[0]["high_level_labels"]), {"Biology", "Informatics"})
        self.assertEqual(records[0]["fine_grained_labels"], ["Sequence analysis"])
        self.assertEqual(records[0]["software_group_id"], records[1]["software_group_id"])

    def test_duplicate_detection_and_view_derivation(self):
        audit = BuildAudit()
        record = {
            "source": "papers_with_code",
            "canonical_record_id": "same",
            "software_group_id": "sw",
            "repository_group_id": "repo",
            "publication_group_id": "pub",
            "source_item_id": "src",
            "source_record_hash": "hash",
            "repository_url_normalized": "https://github.com/a/b",
            "high_level_labels": ["Area"],
            "fine_grained_labels": ["Task"],
        }
        update_record_audits(record, audit, include_missing=True)
        update_record_audits(record, audit, include_missing=True)
        rows = duplicate_rows(audit)
        self.assertTrue(any(row["key_type"] == "canonical_record_id" for row in rows))
        view = view_record(record, "level1_high_level", ["Area"])
        self.assertTrue(view["is_single_label"])
        self.assertFalse(view["is_multi_label"])

    def test_label_statistics_denominators_use_level_cohorts(self):
        audit = BuildAudit()
        records = [
            {
                "source": "papers_with_code",
                "canonical_record_id": "level1-only",
                "repository_url_normalized": "https://github.com/a/one",
                "high_level_labels": ["Area"],
                "fine_grained_labels": [],
            },
            {
                "source": "papers_with_code",
                "canonical_record_id": "level2-only",
                "repository_url_normalized": "https://github.com/a/two",
                "high_level_labels": [],
                "fine_grained_labels": ["Task"],
            },
        ]
        for record in records:
            update_record_audits(record, audit, include_missing=True)
            update_level_view(audit, record, "level1_high_level", record["high_level_labels"])
            update_level_view(audit, record, "level2_fine_grained", record["fine_grained_labels"])

        stats = {(row["source"], row["level"]): row for row in label_stats_rows(audit)}
        self.assertEqual(stats[("papers_with_code", "level1_high_level")]["records"], 1)
        self.assertEqual(stats[("papers_with_code", "level2_fine_grained")]["records"], 1)
        self.assertEqual(audit.level1_counts["papers_with_code"], 1)
        self.assertEqual(audit.level2_counts["papers_with_code"], 1)

    def test_github_cache_fixture_supplies_repository_metadata(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        cache_path = root / "github_repository_cache.jsonl"
        cache_path.write_text(
            (
                '{"repository_url": "https://github.com/Owner/Repo", '
                '"repository_url_normalized": "https://github.com/Owner/Repo", '
                '"repository_title": "Repo", '
                '"repository_description": "Cached description", '
                '"repository_keywords": ["bioinformatics", "workflow"], '
                '"readme_content": "# Cached README", '
                '"error": null}\n'
            ),
            encoding="utf-8",
        )
        audit = BuildAudit()
        github_cache = load_github_metadata_cache(cache_path, audit)
        loader = ArtifactLoader(root / "repository_artifacts", audit, github_cache=github_cache)
        summary = loader.summary_for("https://github.com/Owner/Repo.git")
        self.assertEqual(summary.repository_title, "Repo")
        self.assertEqual(summary.repository_description, "Cached description")
        self.assertEqual(summary.repository_keywords, ["bioinformatics", "workflow"])
        self.assertEqual(summary.readme_content, "# Cached README")
        self.assertEqual(audit.github_artifact_stats["github_cache_hits"], 1)

    def test_group_ids_are_deterministic_and_order_independent(self):
        raw_a = {
            "paper_url": "https://paperswithcode.com/paper/a",
            "github_repo": "https://github.com/example/shared",
            "main_collection_areas": ["Area"],
            "papers with code categories": {"tasks": ["Task A"]},
            "paper_title": "Paper A",
        }
        raw_b = {
            "paper_url": "https://paperswithcode.com/paper/b",
            "github_repo": "https://github.com/example/shared.git",
            "main_collection_areas": ["Area"],
            "papers with code categories": {"tasks": ["Task B"]},
            "paper_title": "Paper B",
        }
        forward = [candidate_pwc_record(raw, self.artifact_loader()) for raw in [raw_a, raw_b]]
        reverse = [candidate_pwc_record(raw, self.artifact_loader()) for raw in [raw_b, raw_a]]
        self.assertEqual(len({record["repository_group_id"] for record in forward}), 1)
        self.assertEqual(len({record["software_group_id"] for record in forward}), 1)
        self.assertEqual(
            {record["source_item_id"]: record["repository_group_id"] for record in forward},
            {record["source_item_id"]: record["repository_group_id"] for record in reverse},
        )

    def test_filter_accounting_and_missing_reasons(self):
        audit = BuildAudit()
        audit.raw_counts["papers_with_code"] = 3
        audit.expanded_counts["papers_with_code"] = 3
        audit.labelled_counts["papers_with_code"] = 2
        audit.retained_counts["papers_with_code"] = 2
        audit.removal_reasons["papers_with_code"]["missing_github_repository"] = 1
        audit.level1_counts["papers_with_code"] = 1
        audit.level_filter_reasons["papers_with_code:level1_high_level"] = Counter(
            {"missing_target_labels_for_level": 1}
        )
        rows = pipeline_stage_rows(audit)
        self.assertTrue(any(row["removed_records"] == 1 for row in rows))
        self.assertEqual(
            missing_reason({"source": "papers_with_code"}, "software_name"),
            "not_applicable",
        )
        self.assertEqual(
            missing_reason({"source": "bio.tools", "repository_url_normalized": "x"}, "readme_content"),
            "failed_enrichment",
        )

    def test_leakage_classification_contains_critical_fields(self):
        leakage = {row["field"]: row["classification"] for row in target_leakage_rows()}
        self.assertEqual(leakage["high_level_labels"], "TARGET")
        self.assertEqual(leakage["pwc_task_labels"], "TARGET")
        self.assertEqual(leakage["edam_topic_labels"], "TARGET")
        self.assertEqual(leakage["repository_url"], "SOURCE_IDENTIFIER")
        self.assertEqual(leakage["software_group_id"], "SOURCE_IDENTIFIER")


if __name__ == "__main__":
    unittest.main()
