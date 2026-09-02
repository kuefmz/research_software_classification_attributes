"""Audit-first canonical dataset builder for the paper dataset.

The functions in this module are intentionally offline. They read only frozen
local inputs, write audit evidence, and build deterministic candidate datasets
for human scientific review.
"""
from __future__ import annotations

import csv
import hashlib
import importlib.metadata
import json
import math
import os
import platform
import re
import statistics
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Iterator, Mapping

from src import config
from src.utils.github_utils import normalize_github_url
from src.utils.publication_utils import doi_url, extract_dois, normalize_doi
from src.utils.somef_utils import repository_slug, simplify_somef_result
from src.utils.text_utils import clean_list, clean_markup_text, clean_text


RDF_RESOURCE = "{http://www.w3.org/1999/02/22-rdf-syntax-ns#}resource"
RDF_ABOUT = "{http://www.w3.org/1999/02/22-rdf-syntax-ns#}about"
OWL_CLASS = "{http://www.w3.org/2002/07/owl#}Class"
OWL_DEPRECATED = "{http://www.w3.org/2002/07/owl#}deprecated"
OWL_ONTOLOGY = "{http://www.w3.org/2002/07/owl#}Ontology"
OWL_VERSION_INFO = "{http://www.w3.org/2002/07/owl#}versionInfo"
OWL_VERSION_IRI = "{http://www.w3.org/2002/07/owl#}versionIRI"
DOAP_VERSION = "{http://usefulinc.com/ns/doap#}Version"
OBO_LEGACY_DATE = "{http://purl.obolibrary.org/obo/}date"
RDFS_LABEL = "{http://www.w3.org/2000/01/rdf-schema#}label"
RDFS_SUBCLASS_OF = "{http://www.w3.org/2000/01/rdf-schema#}subClassOf"
TOPIC_ID_PATTERN = re.compile(r"(topic_\d+)")

GENERIC_LABELS = {"topic", "general", "other", "miscellaneous", "unknown"}
ADMIN_LABEL_PATTERNS = ("obsolete", "deprecated")
PWC_GENERIC_HIGH_LEVEL_LABELS = {"General"}

CANONICAL_FIELDS = [
    "source",
    "source_item_id",
    "canonical_record_id",
    "unit_of_analysis",
    "software_name",
    "software_description",
    "paper_title",
    "paper_abstract",
    "publication_identifier",
    "publication_url",
    "doi",
    "repository_url",
    "repository_url_normalized",
    "repository_urls",
    "repository_title",
    "repository_description",
    "repository_keywords",
    "readme_content",
    "readme_path",
    "somef_description",
    "somef_keywords",
    "somef_json_path",
    "high_level_labels",
    "fine_grained_labels",
    "raw_source_labels",
    "raw_source_label_ids",
    "pwc_area_labels",
    "pwc_task_labels",
    "pwc_method_labels",
    "edam_topic_labels",
    "edam_topic_uris",
    "edam_top_level_labels",
    "edam_top_level_uris",
    "edam_operation_labels",
    "edam_operation_uris",
    "openalex_id",
    "openalex_metadata_error",
    "publication_year",
    "publication_type",
    "source_publication_count",
    "publication_expansion_index",
    "source_record_hash",
    "retention_reason",
]

MISSINGNESS_FIELDS = [
    "software_name",
    "software_description",
    "paper_title",
    "paper_abstract",
    "publication_identifier",
    "publication_url",
    "doi",
    "repository_url",
    "repository_title",
    "repository_description",
    "repository_keywords",
    "readme_content",
    "somef_description",
    "somef_keywords",
    "high_level_labels",
    "fine_grained_labels",
    "pwc_area_labels",
    "pwc_task_labels",
    "edam_topic_labels",
    "edam_topic_uris",
    "edam_top_level_labels",
    "edam_top_level_uris",
]


@dataclass(frozen=True)
class BuildPaths:
    """All paths used by the offline canonical build."""

    base_dir: Path = config.BASE_DIR
    pwc_merged_jsonl: Path = config.PWC_MERGED_JSONL
    biotools_flat_csv: Path = config.BIOTOOLS_FLAT_CSV
    biotools_raw_jsonl: Path = config.BIOTOOLS_RAW_JSONL
    edam_owl: Path = config.RAW_DATA_DIR / "edam" / "EDAM.owl"
    openalex_cache_jsonl: Path = config.BIOTOOLS_PUBLICATION_CACHE_JSONL
    repository_artifacts_dir: Path = config.REPOSITORY_ARTIFACTS_DIR
    somef_manifest_jsonl: Path = config.SOMEF_RUN_MANIFEST_JSONL
    release_dir: Path = config.FINAL_DATA_DIR / "paper_v1"
    mappings_dir: Path = config.DATA_DIR / "mappings"
    reports_dir: Path = config.BASE_DIR / "reports"

    @property
    def tables_dir(self) -> Path:
        return self.reports_dir / "tables"

    @property
    def figures_dir(self) -> Path:
        return self.reports_dir / "figures"


@dataclass
class EdamOntology:
    """Parsed EDAM topic subset."""

    version: str
    metadata: dict[str, str]
    labels: dict[str, str]
    parents: dict[str, set[str]]
    root_topics: set[str]
    path: Path
    sha256: str


@dataclass
class ArtifactSummary:
    """Cached local GitHub/README/SoMEF artifact summary."""

    repository_title: str | None = None
    repository_description: str | None = None
    repository_keywords: list[str] = field(default_factory=list)
    readme_content: str | None = None
    readme_path: str | None = None
    somef_description: str | None = None
    somef_keywords: list[str] = field(default_factory=list)
    somef_json_path: str | None = None
    somef_error: str | None = None
    metadata_error: str | None = None


@dataclass
class KeyAudit:
    """Counter plus examples for duplicate and overlap keys."""

    counts: Counter[str] = field(default_factory=Counter)
    examples: dict[str, list[str]] = field(default_factory=lambda: defaultdict(list))

    def add(self, key: str | None, example: str) -> None:
        if not key:
            return
        self.counts[key] += 1
        if len(self.examples[key]) < 3:
            self.examples[key].append(example)

    def duplicate_rows(self, source: str, key_type: str) -> list[dict[str, Any]]:
        rows = []
        for key, count in self.counts.most_common():
            if count <= 1:
                continue
            rows.append(
                {
                    "source": source,
                    "key_type": key_type,
                    "key_value": key,
                    "record_count": count,
                    "examples": " | ".join(self.examples.get(key, [])),
                }
            )
        return rows


@dataclass
class BuildAudit:
    """Mutable counters collected while building outputs."""

    raw_counts: Counter[str] = field(default_factory=Counter)
    expanded_counts: Counter[str] = field(default_factory=Counter)
    retained_counts: Counter[str] = field(default_factory=Counter)
    level1_counts: Counter[str] = field(default_factory=Counter)
    level2_counts: Counter[str] = field(default_factory=Counter)
    removal_reasons: dict[str, Counter[str]] = field(default_factory=lambda: defaultdict(Counter))
    level_filter_reasons: dict[str, Counter[str]] = field(default_factory=lambda: defaultdict(Counter))
    expansion_added: Counter[str] = field(default_factory=Counter)
    source_publication_distribution: dict[str, Counter[int]] = field(default_factory=lambda: defaultdict(Counter))
    repository_count_distribution: dict[str, Counter[int]] = field(default_factory=lambda: defaultdict(Counter))
    labels_per_record: dict[tuple[str, str], list[int]] = field(default_factory=lambda: defaultdict(list))
    label_support: dict[tuple[str, str], Counter[str]] = field(default_factory=lambda: defaultdict(Counter))
    missing: dict[tuple[str, str], Counter[str]] = field(default_factory=lambda: defaultdict(Counter))
    present: Counter[tuple[str, str]] = field(default_factory=Counter)
    rows_by_source: Counter[str] = field(default_factory=Counter)
    canonical_ids: KeyAudit = field(default_factory=KeyAudit)
    duplicate_audits: dict[tuple[str, str], KeyAudit] = field(default_factory=lambda: defaultdict(KeyAudit))
    repo_sources: dict[str, Counter[str]] = field(default_factory=lambda: defaultdict(Counter))
    doi_sources: dict[str, Counter[str]] = field(default_factory=lambda: defaultdict(Counter))
    name_sources: dict[str, Counter[str]] = field(default_factory=lambda: defaultdict(Counter))
    pwc_task_area_counts: Counter[tuple[str, str]] = field(default_factory=Counter)
    pwc_task_records: Counter[str] = field(default_factory=Counter)
    pwc_area_records: Counter[str] = field(default_factory=Counter)
    pwc_tasks_without_area: Counter[str] = field(default_factory=Counter)
    pwc_areas_without_task: Counter[str] = field(default_factory=Counter)
    pwc_multi_area_records: int = 0
    pwc_multi_task_records: int = 0
    pwc_generic_label_record_count: int = 0
    pwc_generic_label_assignment_count: int = 0
    edam_raw_topic_support: Counter[str] = field(default_factory=Counter)
    edam_high_topic_support: Counter[str] = field(default_factory=Counter)
    edam_mapping_status: Counter[str] = field(default_factory=Counter)
    edam_record_multi_parent_count: int = 0
    openalex_stats: Counter[str] = field(default_factory=Counter)
    github_artifact_stats: Counter[str] = field(default_factory=Counter)
    somef_stats: Counter[str] = field(default_factory=Counter)
    blocking_issues: list[str] = field(default_factory=list)
    review_issues: list[str] = field(default_factory=list)


def atomic_write_text(path: Path, text: str) -> None:
    """Write text atomically."""

    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as tmp:
        tmp.write(text)
        tmp_path = Path(tmp.name)
    os.replace(tmp_path, path)


def atomic_jsonl_writer(path: Path):
    """Context manager yielding a write function for sorted-key JSONL records."""

    class Writer:
        def __init__(self, target: Path) -> None:
            self.target = target
            self.count = 0
            self.tmp_path: Path | None = None
            self.handle = None

        def __enter__(self):
            self.target.parent.mkdir(parents=True, exist_ok=True)
            self.handle = tempfile.NamedTemporaryFile(
                "w", encoding="utf-8", dir=self.target.parent, delete=False
            )
            self.tmp_path = Path(self.handle.name)
            return self

        def write(self, record: Mapping[str, Any]) -> None:
            assert self.handle is not None
            self.handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
            self.count += 1

        def __exit__(self, exc_type, exc, tb) -> None:
            assert self.handle is not None
            assert self.tmp_path is not None
            self.handle.close()
            if exc_type is None:
                os.replace(self.tmp_path, self.target)
            elif self.tmp_path.exists():
                self.tmp_path.unlink()

    return Writer(path)


def write_csv_rows(path: Path, rows: Iterable[Mapping[str, Any]], fieldnames: list[str] | None = None) -> int:
    """Write dictionaries to CSV with JSON encoding for nested values."""

    materialized = list(rows)
    if fieldnames is None:
        fieldnames = []
        for row in materialized:
            for key in row:
                if key not in fieldnames:
                    fieldnames.append(key)
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", newline="", dir=path.parent, delete=False) as tmp:
        tmp_path = Path(tmp.name)
        writer = csv.DictWriter(tmp, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in materialized:
            writer.writerow({key: csv_value(row.get(key)) for key in fieldnames})
    os.replace(tmp_path, path)
    return len(materialized)


def csv_value(value: Any) -> Any:
    if isinstance(value, (list, dict, tuple, set)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return value


def read_jsonl(path: Path) -> Iterator[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSON in {path}:{line_number}") from exc


def read_csv_dicts(path: Path) -> Iterator[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        yield from csv.DictReader(handle)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def deterministic_id(*parts: Any, length: int = 24) -> str:
    """Create a stable identifier independent of row order and timestamps."""

    raw = "\x1f".join(clean_text(part) or "" for part in parts)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:length]


def normalized_name(value: Any) -> str | None:
    text = clean_text(value)
    if not text:
        return None
    normalized = re.sub(r"[^a-z0-9]+", " ", text.casefold()).strip()
    return normalized or None


def record_hash(record: Mapping[str, Any]) -> str:
    """Hash a compact normalized view of one source observation."""

    payload = {
        key: record.get(key)
        for key in [
            "source",
            "source_item_id",
            "doi",
            "publication_url",
            "repository_url_normalized",
            "high_level_labels",
            "fine_grained_labels",
            "paper_title",
            "software_name",
        ]
    }
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def topic_id(value: Any) -> str | None:
    if not value:
        return None
    match = TOPIC_ID_PATTERN.search(str(value))
    return match.group(1) if match else None


def canonical_topic_uri(topic: str | None) -> str | None:
    return f"http://edamontology.org/{topic}" if topic else None


def is_generic_or_admin_label(label: str | None) -> bool:
    normalized = (label or "").strip().casefold()
    if not normalized or normalized in GENERIC_LABELS:
        return True
    return any(pattern in normalized for pattern in ADMIN_LABEL_PATTERNS)


def parse_bool(text: str | None) -> bool:
    return (text or "").strip().casefold() in {"true", "1"}


def ontology_metadata(root: ET.Element) -> dict[str, str]:
    ontology = root.find(f".//{OWL_ONTOLOGY}")
    if ontology is None:
        return {"version": "unknown", "version_iri": "unknown", "date": "unknown"}
    version_info = clean_text(ontology.findtext(OWL_VERSION_INFO)) or "unknown"
    version_iri = clean_text(ontology.attrib.get(OWL_VERSION_IRI)) or "unknown"
    doap_version = clean_text(ontology.findtext(DOAP_VERSION)) or "unknown"
    ontology_date = clean_text(ontology.findtext(OBO_LEGACY_DATE)) or "unknown"
    version = version_info
    if version == "unknown" and version_iri != "unknown":
        version = version_iri
    if version == "unknown" and doap_version != "unknown":
        version = doap_version
    return {
        "version": version,
        "version_info": version_info,
        "version_iri": version_iri,
        "doap_version": doap_version,
        "date": ontology_date,
    }


def parse_edam_ontology(path: Path) -> EdamOntology:
    """Parse EDAM topic labels and parent edges from a frozen local OWL file."""

    tree = ET.parse(path)
    root = tree.getroot()
    metadata = ontology_metadata(root)
    labels: dict[str, str] = {}
    parents: dict[str, set[str]] = defaultdict(set)
    deprecated: set[str] = set()

    for klass in root.findall(f".//{OWL_CLASS}"):
        current_topic = topic_id(klass.attrib.get(RDF_ABOUT))
        if not current_topic:
            continue
        label = clean_text(klass.findtext(RDFS_LABEL)) or current_topic
        labels[current_topic] = label
        if parse_bool(klass.findtext(OWL_DEPRECATED)):
            deprecated.add(current_topic)
        for parent in klass.findall(RDFS_SUBCLASS_OF):
            parent_topic = topic_id(parent.attrib.get(RDF_RESOURCE))
            if parent_topic:
                parents[current_topic].add(parent_topic)

    active_labels = {
        topic: label
        for topic, label in labels.items()
        if topic not in deprecated and not any(pattern in label.casefold() for pattern in ADMIN_LABEL_PATTERNS)
    }
    active_parents = {
        topic: {parent for parent in parents.get(topic, set()) if parent in active_labels}
        for topic in active_labels
    }
    root_topics = {topic for topic, label in active_labels.items() if label.strip().casefold() == "topic"}
    return EdamOntology(
        version=metadata["version"],
        metadata=metadata,
        labels=active_labels,
        parents=active_parents,
        root_topics=root_topics,
        path=path,
        sha256=sha256_file(path),
    )


def edam_top_level_mappings(topic: str, ontology: EdamOntology) -> list[dict[str, str | None]]:
    """Return all top-level EDAM mappings for one topic, preserving paths."""

    if topic not in ontology.labels:
        return [
            {
                "high_level_topic": None,
                "mapping_path": topic,
                "mapping_status": "unmapped_topic_not_in_ontology",
            }
        ]
    if topic in ontology.root_topics or is_generic_or_admin_label(ontology.labels.get(topic)):
        return [
            {
                "high_level_topic": None,
                "mapping_path": topic,
                "mapping_status": "excluded_generic_or_admin_topic",
            }
        ]

    results: list[dict[str, str | None]] = []

    def walk(current: str, path: tuple[str, ...]) -> None:
        parents = sorted(parent for parent in ontology.parents.get(current, set()) if parent in ontology.labels)
        if not parents:
            results.append(
                {
                    "high_level_topic": current,
                    "mapping_path": " > ".join(path),
                    "mapping_status": "mapped_without_root_path",
                }
            )
            return
        for parent in parents:
            if parent in path:
                results.append(
                    {
                        "high_level_topic": None,
                        "mapping_path": " > ".join((*path, parent)),
                        "mapping_status": "cycle_detected",
                    }
                )
                continue
            if parent in ontology.root_topics or is_generic_or_admin_label(ontology.labels.get(parent)):
                results.append(
                    {
                        "high_level_topic": current,
                        "mapping_path": " > ".join((*path, parent)),
                        "mapping_status": "mapped",
                    }
                )
            else:
                walk(parent, (*path, parent))

    walk(topic, (topic,))

    deduped: list[dict[str, str | None]] = []
    seen: set[tuple[str | None, str, str | None]] = set()
    for result in results:
        key = (result["high_level_topic"], result["mapping_path"], result["mapping_status"])
        if key not in seen:
            seen.add(key)
            deduped.append(result)
    return deduped


def build_edam_mapping_rows(ontology: EdamOntology) -> list[dict[str, Any]]:
    rows = []
    for detailed_topic in sorted(ontology.labels):
        for mapping in edam_top_level_mappings(detailed_topic, ontology):
            high = mapping["high_level_topic"]
            path_ids = str(mapping["mapping_path"] or "").split(" > ") if mapping["mapping_path"] else []
            rows.append(
                {
                    "detailed_topic_uri": canonical_topic_uri(detailed_topic),
                    "detailed_topic_id": detailed_topic,
                    "detailed_topic_label": ontology.labels.get(detailed_topic),
                    "high_level_topic_uri": canonical_topic_uri(high),
                    "high_level_topic_id": high,
                    "high_level_topic_label": ontology.labels.get(high) if high else None,
                    "mapping_path": " > ".join(ontology.labels.get(item, item) for item in path_ids),
                    "mapping_path_ids": mapping["mapping_path"],
                    "mapping_status": mapping["mapping_status"],
                }
            )
    return rows


def split_pipe(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return clean_list(value)
    return [part.strip() for part in str(value).split("|") if part.strip()]


def category(record: Mapping[str, Any], name: str) -> Any:
    categories = record.get("papers with code categories") or {}
    if isinstance(categories, dict):
        return categories.get(name)
    return None


def pwc_methods(record: Mapping[str, Any]) -> list[str]:
    methods: list[Any] = []
    for method in category(record, "methods") or []:
        if isinstance(method, dict):
            methods.append(method.get("method") or method.get("method_full_name") or method.get("name"))
        else:
            methods.append(method)
    return clean_list(methods)


def raw_source_hash(record: Mapping[str, Any]) -> str:
    raw = json.dumps(record, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def pwc_publication_url(record: Mapping[str, Any]) -> str | None:
    return (
        clean_text(record.get("url_abs"))
        or clean_text(record.get("paper_url"))
        or clean_text(record.get("url_pdf"))
    )


def pwc_repository_urls(record: Mapping[str, Any]) -> list[str]:
    values: list[Any] = []
    values.append(record.get("github_repo"))
    values.extend(clean_list(record.get("github_repos")))
    for item in record.get("repository_links") or []:
        if isinstance(item, dict):
            values.append(item.get("url") or item.get("repository_url"))
        else:
            values.append(item)
    normalized: list[str] = []
    for value in values:
        repo = normalize_github_url(clean_text(value))
        if repo and repo not in normalized:
            normalized.append(repo)
    return normalized


def raw_biotools_lookup(path: Path) -> dict[str, dict[str, Any]]:
    return {row.get("biotoolsID"): row for row in read_jsonl(path) if row.get("biotoolsID")}


def github_urls_from_biotools(raw_tool: Mapping[str, Any] | None, flat_row: Mapping[str, Any]) -> list[str]:
    values: list[Any] = [flat_row.get("github_url"), flat_row.get("homepage")]
    if raw_tool:
        values.append(raw_tool.get("homepage"))
        for field_name in ("link", "download", "documentation"):
            for item in raw_tool.get(field_name) or []:
                if isinstance(item, dict):
                    values.append(item.get("url"))
    repos: list[str] = []
    for value in values:
        repo = normalize_github_url(clean_text(value))
        if repo and repo not in repos:
            repos.append(repo)
    return repos


def biotools_publication_dois(flat_row: Mapping[str, Any], raw_tool: Mapping[str, Any] | None) -> list[str]:
    dois = extract_dois(flat_row.get("doi"))
    if raw_tool:
        for publication in raw_tool.get("publication") or []:
            if isinstance(publication, dict):
                for doi in extract_dois(publication.get("doi")):
                    if doi not in dois:
                        dois.append(doi)
    return dois


def biotools_operations(raw_tool: Mapping[str, Any] | None, flat_row: Mapping[str, Any]) -> tuple[list[str], list[str]]:
    labels: list[str] = []
    uris: list[str] = []
    if raw_tool:
        for function in raw_tool.get("function") or []:
            if not isinstance(function, dict):
                continue
            for operation in function.get("operation") or []:
                if isinstance(operation, dict):
                    label = clean_text(operation.get("term"))
                    uri = clean_text(operation.get("uri"))
                    if label and label not in labels:
                        labels.append(label)
                    if uri and uri not in uris:
                        uris.append(uri)
    if not labels:
        labels = clean_list(flat_row.get("operation_terms") or flat_row.get("function_text"))
    return labels, uris


def load_openalex_cache(path: Path, audit: BuildAudit) -> dict[str, dict[str, Any]]:
    cache: dict[str, dict[str, Any]] = {}
    if not path.exists():
        audit.openalex_stats["cache_missing"] += 1
        return cache
    for row in read_jsonl(path):
        requested = normalize_doi(row.get("doi"))
        if not requested:
            audit.openalex_stats["rows_without_requested_doi"] += 1
            continue
        audit.openalex_stats["cache_rows"] += 1
        if requested in cache:
            audit.openalex_stats["duplicate_requested_doi_rows"] += 1
        cache[requested] = row
        if row.get("metadata_error"):
            audit.openalex_stats[f"metadata_error:{row.get('metadata_error')}"] += 1
        else:
            audit.openalex_stats["metadata_success"] += 1
        returned = normalize_doi(row.get("openalex_doi") or row.get("publication_url"))
        if returned and returned != requested:
            audit.openalex_stats["requested_returned_doi_mismatch"] += 1
    return cache


class ArtifactLoader:
    """Lazy loader for saved GitHub README and SoMEF artifacts."""

    def __init__(self, root: Path, audit: BuildAudit, max_cache_size: int = 2048) -> None:
        self.root = root
        self.audit = audit
        self.max_cache_size = max_cache_size
        self.cache: dict[str, ArtifactSummary] = {}
        self.order: list[str] = []

    def summary_for(self, repository_url: str | None) -> ArtifactSummary:
        if not repository_url:
            return ArtifactSummary()
        normalized = normalize_github_url(repository_url)
        if not normalized:
            return ArtifactSummary()
        if normalized in self.cache:
            return self.cache[normalized]
        summary = self._load(normalized)
        self.cache[normalized] = summary
        self.order.append(normalized)
        if len(self.order) > self.max_cache_size:
            old = self.order.pop(0)
            self.cache.pop(old, None)
        return summary

    def _load(self, normalized: str) -> ArtifactSummary:
        artifact_dir = self.root / repository_slug(normalized)
        metadata_path = artifact_dir / "metadata.json"
        readme_path = artifact_dir / "README.md"
        somef_path = artifact_dir / "somef.json"
        summary = ArtifactSummary()
        if metadata_path.exists():
            try:
                metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError as exc:
                metadata = {"error": f"invalid_metadata_json:{exc}"}
            summary.repository_title = clean_text(metadata.get("repository_title"))
            summary.repository_description = clean_markup_text(metadata.get("repository_description"))
            summary.repository_keywords = clean_list(metadata.get("repository_keywords") or metadata.get("topics"))
            summary.metadata_error = clean_text(metadata.get("error"))
        if readme_path.exists():
            summary.readme_path = str(readme_path)
            summary.readme_content = readme_path.read_text(encoding="utf-8", errors="replace")
        if somef_path.exists():
            summary.somef_json_path = str(somef_path)
            try:
                raw_somef = json.loads(somef_path.read_text(encoding="utf-8"))
                simplified = simplify_somef_result(raw_somef) if isinstance(raw_somef, dict) else {}
                summary.somef_description = clean_markup_text(simplified.get("somef_description"))
                summary.somef_keywords = clean_list(simplified.get("keywords"))
                summary.somef_error = clean_text(raw_somef.get("error") if isinstance(raw_somef, dict) else None)
                if not summary.repository_title:
                    summary.repository_title = clean_text(simplified.get("title"))
            except json.JSONDecodeError as exc:
                summary.somef_error = f"invalid_somef_json:{exc}"
        if not summary.repository_title:
            summary.repository_title = normalized.rstrip("/").split("/")[-1]
        return summary


def audit_repository_artifacts(paths: BuildPaths, audit: BuildAudit) -> None:
    root = paths.repository_artifacts_dir
    if not root.exists():
        audit.github_artifact_stats["artifact_root_missing"] += 1
        return
    for artifact_dir in root.iterdir():
        if not artifact_dir.is_dir():
            continue
        audit.github_artifact_stats["artifact_directories"] += 1
        metadata_path = artifact_dir / "metadata.json"
        readme_path = artifact_dir / "README.md"
        somef_path = artifact_dir / "somef.json"
        if readme_path.exists() and readme_path.stat().st_size > 0:
            audit.github_artifact_stats["readme_files"] += 1
        else:
            audit.github_artifact_stats["missing_readme_files"] += 1
        if metadata_path.exists():
            audit.github_artifact_stats["metadata_files"] += 1
            try:
                json.loads(metadata_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                audit.github_artifact_stats["invalid_metadata_json"] += 1
        else:
            audit.github_artifact_stats["missing_metadata_files"] += 1
        if somef_path.exists():
            audit.somef_stats["somef_json_files"] += 1
            try:
                raw = json.loads(somef_path.read_text(encoding="utf-8"))
                if isinstance(raw, dict) and raw.get("error"):
                    audit.somef_stats["somef_error_json_files"] += 1
                elif isinstance(raw, dict):
                    audit.somef_stats["somef_success_json_files"] += 1
            except json.JSONDecodeError:
                audit.somef_stats["invalid_somef_json"] += 1
        else:
            audit.somef_stats["missing_somef_json_files"] += 1

    if paths.somef_manifest_jsonl.exists():
        for row in read_jsonl(paths.somef_manifest_jsonl):
            artifact_type = clean_text(row.get("artifact_type")) or "unknown"
            status = clean_text(row.get("status")) or "unknown"
            audit.somef_stats[f"manifest:{artifact_type}:{status}"] += 1


def mapping_lookup_from_rows(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    lookup: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        topic = row.get("detailed_topic_id")
        if topic:
            lookup[topic].append(row)
    return lookup


def edam_map_labels(
    labels: list[str],
    uris: list[str],
    ontology: EdamOntology,
    mapping_lookup: dict[str, list[dict[str, Any]]],
) -> tuple[list[str], list[str], list[str]]:
    """Map detailed EDAM topics to high-level topics, preserving multi-maps."""

    label_to_topics: dict[str, list[str]] = defaultdict(list)
    for topic, label in ontology.labels.items():
        label_to_topics[label.casefold()].append(topic)

    high_by_uri: dict[str, str] = {}
    statuses: list[str] = []
    pairs = list(zip(labels, uris))
    if not pairs:
        pairs = [(label, "") for label in labels]
    for label, uri in pairs:
        raw_topic = topic_id(uri)
        if not raw_topic and label:
            candidates = label_to_topics.get(label.casefold(), [])
            if len(candidates) == 1:
                raw_topic = candidates[0]
            elif len(candidates) > 1:
                statuses.append("ambiguous_label_without_uri")
                continue
        if not raw_topic:
            statuses.append("missing_topic_uri")
            continue
        rows = mapping_lookup.get(raw_topic)
        if not rows:
            statuses.append("unmapped_topic_not_in_ontology")
            continue
        valid = False
        for row in rows:
            statuses.append(str(row.get("mapping_status")))
            high_label = clean_text(row.get("high_level_topic_label"))
            high_uri = clean_text(row.get("high_level_topic_uri"))
            if high_label and high_uri and not is_generic_or_admin_label(high_label):
                high_by_uri[high_uri] = high_label
                valid = True
        if not valid:
            statuses.append("no_usable_high_level_topic")
    return list(high_by_uri.values()), list(high_by_uri.keys()), statuses


def record_value_present(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, (list, tuple, set, dict)):
        return bool(value)
    text = clean_text(value)
    return bool(text)


def missing_reason(record: Mapping[str, Any], field: str) -> str:
    source = record.get("source")
    if source == "papers_with_code" and field.startswith("edam_"):
        return "not_applicable"
    if source == "bio.tools" and field.startswith("pwc_"):
        return "not_applicable"
    if source == "papers_with_code" and field in {"software_name", "software_description"}:
        return "not_applicable"
    if field in {"repository_title", "repository_description", "repository_keywords", "readme_content"}:
        return "failed_enrichment" if record.get("repository_url_normalized") else "genuinely_absent_in_source"
    if field in {"somef_description", "somef_keywords"}:
        return "failed_enrichment" if record.get("repository_url_normalized") else "genuinely_absent_in_source"
    if source == "bio.tools" and field in {"paper_title", "paper_abstract"} and record.get("doi"):
        return "failed_enrichment" if record.get("openalex_metadata_error") else "genuinely_absent_in_source"
    if field in {"publication_identifier", "publication_url", "doi"}:
        return "genuinely_absent_in_source"
    return "empty_after_cleaning"


def update_record_audits(record: Mapping[str, Any], audit: BuildAudit, include_missing: bool) -> None:
    source = str(record.get("source"))
    example = str(record.get("canonical_record_id") or record.get("source_item_id"))
    if not include_missing:
        audit.duplicate_audits[(source, "source_item_id")].add(clean_text(record.get("source_item_id")), example)
        audit.duplicate_audits[(source, "doi")].add(normalize_doi(record.get("doi")), example)
        audit.duplicate_audits[(source, "repository_url")].add(clean_text(record.get("repository_url_normalized")), example)
        audit.duplicate_audits[(source, "software_name")].add(normalized_name(record.get("software_name") or record.get("repository_title")), example)
        title_repo = "|".join(
            [
                normalized_name(record.get("paper_title")) or "",
                clean_text(record.get("repository_url_normalized")) or "",
            ]
        )
        audit.duplicate_audits[(source, "title_repository")].add(title_repo if title_repo.strip("|") else None, example)
        audit.duplicate_audits[(source, "exact_record_hash")].add(clean_text(record.get("source_record_hash")), example)

        repo = clean_text(record.get("repository_url_normalized"))
        if repo:
            audit.repo_sources[repo][source] += 1
        doi = normalize_doi(record.get("doi"))
        if doi:
            audit.doi_sources[doi][source] += 1
        name = normalized_name(record.get("software_name") or record.get("repository_title"))
        if name:
            audit.name_sources[name][source] += 1
        return

    audit.canonical_ids.add(clean_text(record.get("canonical_record_id")), example)
    for label in clean_list(record.get("high_level_labels")):
        audit.label_support[(source, "level1_high_level")][label] += 1
    for label in clean_list(record.get("fine_grained_labels")):
        audit.label_support[(source, "level2_fine_grained")][label] += 1
    audit.labels_per_record[(source, "level1_high_level")].append(len(clean_list(record.get("high_level_labels"))))
    audit.labels_per_record[(source, "level2_fine_grained")].append(len(clean_list(record.get("fine_grained_labels"))))

    audit.rows_by_source[source] += 1
    for field_name in MISSINGNESS_FIELDS:
        if record_value_present(record.get(field_name)):
            audit.present[(source, field_name)] += 1
        else:
            audit.missing[(source, field_name)][missing_reason(record, field_name)] += 1


def add_pwc_hierarchy_audit(record: Mapping[str, Any], audit: BuildAudit) -> None:
    areas = clean_list(record.get("pwc_area_labels"))
    tasks = clean_list(record.get("pwc_task_labels"))
    if len(areas) > 1:
        audit.pwc_multi_area_records += 1
    if len(tasks) > 1:
        audit.pwc_multi_task_records += 1
    for area in areas:
        audit.pwc_area_records[area] += 1
    for task in tasks:
        audit.pwc_task_records[task] += 1
    if tasks and not areas:
        for task in tasks:
            audit.pwc_tasks_without_area[task] += 1
    if areas and not tasks:
        for area in areas:
            audit.pwc_areas_without_task[area] += 1
    for area in areas:
        for task in tasks:
            audit.pwc_task_area_counts[(task, area)] += 1


def candidate_pwc_record(raw: Mapping[str, Any], artifact_loader: ArtifactLoader) -> dict[str, Any]:
    publication_url = pwc_publication_url(raw)
    repository_urls = pwc_repository_urls(raw)
    repository_url = repository_urls[0] if repository_urls else None
    artifact = artifact_loader.summary_for(repository_url)
    area_labels = clean_list(raw.get("main_collection_areas") or raw.get("main_collection_area") or category(raw, "main_collection_areas"))
    high_level_labels = [label for label in area_labels if label not in PWC_GENERIC_HIGH_LEVEL_LABELS]
    task_labels = clean_list(category(raw, "tasks"))
    doi_values: list[str] = []
    for field_name in ("doi", "paper_url", "url_abs", "url_pdf", "publication_url"):
        for doi in extract_dois(raw.get(field_name)):
            if doi not in doi_values:
                doi_values.append(doi)
    source_item_id = clean_text(raw.get("paper_url")) or clean_text(raw.get("arxiv_id")) or deterministic_id(
        "papers_with_code", raw.get("paper_title"), publication_url
    )
    row = {
        "source": "papers_with_code",
        "source_item_id": source_item_id,
        "canonical_record_id": deterministic_id("papers_with_code", source_item_id, repository_url, publication_url),
        "unit_of_analysis": "papers_with_code_source_paper_record",
        "software_name": None,
        "software_description": None,
        "paper_title": clean_markup_text(raw.get("paper_title")),
        "paper_abstract": clean_markup_text(raw.get("abstract") or raw.get("short_abstract")),
        "publication_identifier": doi_values[0] if doi_values else clean_text(raw.get("arxiv_id")),
        "publication_url": publication_url,
        "doi": doi_values[0] if doi_values else None,
        "repository_url": repository_url,
        "repository_url_normalized": repository_url,
        "repository_urls": repository_urls,
        "repository_title": artifact.repository_title,
        "repository_description": artifact.repository_description,
        "repository_keywords": artifact.repository_keywords,
        "readme_content": artifact.readme_content,
        "readme_path": artifact.readme_path,
        "somef_description": artifact.somef_description,
        "somef_keywords": artifact.somef_keywords,
        "somef_json_path": artifact.somef_json_path,
        "high_level_labels": high_level_labels,
        "fine_grained_labels": task_labels,
        "raw_source_labels": [*area_labels, *task_labels],
        "raw_source_label_ids": [],
        "pwc_area_labels": area_labels,
        "pwc_task_labels": task_labels,
        "pwc_method_labels": pwc_methods(raw),
        "edam_topic_labels": [],
        "edam_topic_uris": [],
        "edam_top_level_labels": [],
        "edam_top_level_uris": [],
        "edam_operation_labels": [],
        "edam_operation_uris": [],
        "openalex_id": None,
        "openalex_metadata_error": None,
        "publication_year": None,
        "publication_type": None,
        "source_publication_count": 1 if publication_url else 0,
        "publication_expansion_index": 1 if publication_url else 0,
        "source_record_hash": raw_source_hash(raw),
        "retention_reason": "candidate",
    }
    return row


def candidate_biotools_records(
    flat_row: Mapping[str, Any],
    raw_tool: Mapping[str, Any] | None,
    ontology: EdamOntology,
    edam_mapping_lookup: dict[str, list[dict[str, Any]]],
    openalex_cache: Mapping[str, Mapping[str, Any]],
    artifact_loader: ArtifactLoader,
) -> list[dict[str, Any]]:
    biotools_id = clean_text(flat_row.get("biotools_id")) or clean_text((raw_tool or {}).get("biotoolsID"))
    repository_urls = github_urls_from_biotools(raw_tool, flat_row)
    repository_url = repository_urls[0] if repository_urls else None
    artifact = artifact_loader.summary_for(repository_url)
    topic_labels = split_pipe(flat_row.get("topic_terms"))
    topic_uris = split_pipe(flat_row.get("topic_uris"))
    if raw_tool and not topic_labels:
        topic_labels = clean_list(topic.get("term") for topic in raw_tool.get("topic") or [] if isinstance(topic, dict))
        topic_uris = clean_list(topic.get("uri") for topic in raw_tool.get("topic") or [] if isinstance(topic, dict))
    high_labels, high_uris, statuses = edam_map_labels(topic_labels, topic_uris, ontology, edam_mapping_lookup)
    operation_labels, operation_uris = biotools_operations(raw_tool, flat_row)
    dois = biotools_publication_dois(flat_row, raw_tool)
    expansions = dois or [None]
    publication_count = len(expansions)
    output = []
    for index, doi in enumerate(expansions, start=1):
        metadata = openalex_cache.get(doi or "", {}) if doi else {}
        paper_title = clean_markup_text(flat_row.get("paper_title") or flat_row.get("publication_note"))
        paper_abstract = clean_markup_text(flat_row.get("abstract"))
        if metadata:
            paper_title = clean_markup_text(metadata.get("paper_title")) or paper_title
            paper_abstract = clean_markup_text(metadata.get("paper_abstract")) or paper_abstract
        source_item_id = f"{biotools_id}::doi::{doi}" if doi else str(biotools_id)
        row = {
            "source": "bio.tools",
            "source_item_id": source_item_id,
            "canonical_record_id": deterministic_id("bio.tools", biotools_id, doi or "no_doi", repository_url),
            "unit_of_analysis": "biotools_tool_publication_observation" if doi else "biotools_tool_observation_without_doi",
            "software_name": clean_text(flat_row.get("name") or (raw_tool or {}).get("name")),
            "software_description": clean_markup_text(flat_row.get("description") or (raw_tool or {}).get("description")),
            "paper_title": paper_title,
            "paper_abstract": paper_abstract,
            "publication_identifier": doi or clean_text(flat_row.get("pmid")) or clean_text(flat_row.get("pmcid")),
            "publication_url": doi_url(doi) if doi else None,
            "doi": doi,
            "repository_url": repository_url,
            "repository_url_normalized": repository_url,
            "repository_urls": repository_urls,
            "repository_title": artifact.repository_title or clean_text(flat_row.get("repo_title")),
            "repository_description": artifact.repository_description,
            "repository_keywords": artifact.repository_keywords,
            "readme_content": artifact.readme_content,
            "readme_path": artifact.readme_path,
            "somef_description": artifact.somef_description,
            "somef_keywords": artifact.somef_keywords,
            "somef_json_path": artifact.somef_json_path,
            "high_level_labels": high_labels,
            "fine_grained_labels": topic_labels,
            "raw_source_labels": topic_labels,
            "raw_source_label_ids": topic_uris,
            "pwc_area_labels": [],
            "pwc_task_labels": [],
            "pwc_method_labels": [],
            "edam_topic_labels": topic_labels,
            "edam_topic_uris": topic_uris,
            "edam_top_level_labels": high_labels,
            "edam_top_level_uris": high_uris,
            "edam_operation_labels": operation_labels,
            "edam_operation_uris": operation_uris,
            "openalex_id": metadata.get("openalex_id"),
            "openalex_metadata_error": metadata.get("metadata_error"),
            "publication_year": metadata.get("publication_year"),
            "publication_type": metadata.get("publication_type"),
            "source_publication_count": publication_count,
            "publication_expansion_index": index,
            "source_record_hash": raw_source_hash(flat_row),
            "retention_reason": "candidate",
            "edam_mapping_statuses": sorted(set(statuses)),
        }
        output.append(row)
    return output


def retention_reason(record: Mapping[str, Any]) -> str:
    if not record.get("repository_url_normalized"):
        return "missing_github_repository"
    if not clean_list(record.get("high_level_labels")) and not clean_list(record.get("fine_grained_labels")):
        return "missing_all_target_labels"
    return "retained"


def view_record(record: Mapping[str, Any], target_level: str, target_labels: list[str]) -> dict[str, Any]:
    row = dict(record)
    row["target_level"] = target_level
    row["target_labels"] = target_labels
    row["is_single_label"] = len(target_labels) == 1
    row["is_multi_label"] = len(target_labels) > 1
    return row


def update_level_view(audit: BuildAudit, record: Mapping[str, Any], level: str, labels: list[str]) -> None:
    source = str(record.get("source"))
    if labels:
        if level == "level1_high_level":
            audit.level1_counts[source] += 1
        else:
            audit.level2_counts[source] += 1
    else:
        audit.level_filter_reasons[f"{source}:{level}"]["missing_target_labels_for_level"] += 1


def build_datasets(paths: BuildPaths, audit: BuildAudit) -> dict[str, Any]:
    """Build master and level-specific candidate datasets while auditing."""

    required = [
        paths.pwc_merged_jsonl,
        paths.biotools_flat_csv,
        paths.biotools_raw_jsonl,
        paths.edam_owl,
    ]
    missing_required = [str(path) for path in required if not path.exists()]
    if missing_required:
        raise FileNotFoundError("Missing frozen input(s): " + ", ".join(missing_required))

    paths.release_dir.mkdir(parents=True, exist_ok=True)
    paths.mappings_dir.mkdir(parents=True, exist_ok=True)
    paths.reports_dir.mkdir(parents=True, exist_ok=True)
    paths.tables_dir.mkdir(parents=True, exist_ok=True)
    paths.figures_dir.mkdir(parents=True, exist_ok=True)

    ontology = parse_edam_ontology(paths.edam_owl)
    edam_mapping_rows = build_edam_mapping_rows(ontology)
    edam_mapping_lookup = mapping_lookup_from_rows(edam_mapping_rows)
    write_csv_rows(paths.mappings_dir / "edam_detailed_to_high_level.csv", edam_mapping_rows)

    openalex_cache = load_openalex_cache(paths.openalex_cache_jsonl, audit)
    audit_repository_artifacts(paths, audit)
    artifact_loader = ArtifactLoader(paths.repository_artifacts_dir, audit)

    raw_biotools = raw_biotools_lookup(paths.biotools_raw_jsonl)

    master_path = paths.release_dir / "master_dataset.jsonl"
    level1_path = paths.release_dir / "level1_high_level.jsonl"
    level2_path = paths.release_dir / "level2_fine_grained.jsonl"

    with atomic_jsonl_writer(master_path) as master_writer, atomic_jsonl_writer(level1_path) as level1_writer, atomic_jsonl_writer(level2_path) as level2_writer:
        for raw in read_jsonl(paths.pwc_merged_jsonl):
            audit.raw_counts["papers_with_code"] += 1
            audit.expanded_counts["papers_with_code"] += 1
            record = candidate_pwc_record(raw, artifact_loader)
            audit.repository_count_distribution["papers_with_code"][len(clean_list(record.get("repository_urls")))] += 1
            audit.source_publication_distribution["papers_with_code"][1 if record.get("publication_url") else 0] += 1
            if any(label in PWC_GENERIC_HIGH_LEVEL_LABELS for label in clean_list(record.get("pwc_area_labels"))):
                audit.pwc_generic_label_record_count += 1
                audit.pwc_generic_label_assignment_count += sum(
                    label in PWC_GENERIC_HIGH_LEVEL_LABELS for label in clean_list(record.get("pwc_area_labels"))
                )
            add_pwc_hierarchy_audit(record, audit)
            update_record_audits(record, audit, include_missing=False)
            reason = retention_reason(record)
            if reason != "retained":
                audit.removal_reasons["papers_with_code"][reason] += 1
                continue
            record["retention_reason"] = "retained_for_canonical_master"
            audit.retained_counts["papers_with_code"] += 1
            master_writer.write({field_name: record.get(field_name) for field_name in CANONICAL_FIELDS})
            update_record_audits(record, audit, include_missing=True)
            high = clean_list(record.get("high_level_labels"))
            fine = clean_list(record.get("fine_grained_labels"))
            update_level_view(audit, record, "level1_high_level", high)
            update_level_view(audit, record, "level2_fine_grained", fine)
            if high:
                level1_writer.write(view_record(record, "level1_high_level", high))
            if fine:
                level2_writer.write(view_record(record, "level2_fine_grained", fine))

        for flat_row in read_csv_dicts(paths.biotools_flat_csv):
            audit.raw_counts["bio.tools"] += 1
            raw_tool = raw_biotools.get(flat_row.get("biotools_id"))
            records = candidate_biotools_records(
                flat_row,
                raw_tool,
                ontology,
                edam_mapping_lookup,
                openalex_cache,
                artifact_loader,
            )
            audit.expanded_counts["bio.tools"] += len(records)
            if len(records) > 1:
                audit.expansion_added["bio.tools"] += len(records) - 1
            audit.source_publication_distribution["bio.tools"][len(records)] += 1
            for record in records:
                audit.repository_count_distribution["bio.tools"][len(clean_list(record.get("repository_urls")))] += 1
                for label in clean_list(record.get("edam_topic_labels")):
                    audit.edam_raw_topic_support[label] += 1
                for label in clean_list(record.get("edam_top_level_labels")):
                    audit.edam_high_topic_support[label] += 1
                for status in clean_list(record.get("edam_mapping_statuses")):
                    audit.edam_mapping_status[status] += 1
                if len(clean_list(record.get("edam_top_level_labels"))) > 1:
                    audit.edam_record_multi_parent_count += 1
                update_record_audits(record, audit, include_missing=False)
                reason = retention_reason(record)
                if reason != "retained":
                    audit.removal_reasons["bio.tools"][reason] += 1
                    continue
                record["retention_reason"] = "retained_for_canonical_master"
                audit.retained_counts["bio.tools"] += 1
                master_writer.write({field_name: record.get(field_name) for field_name in CANONICAL_FIELDS})
                update_record_audits(record, audit, include_missing=True)
                high = clean_list(record.get("high_level_labels"))
                fine = clean_list(record.get("fine_grained_labels"))
                update_level_view(audit, record, "level1_high_level", high)
                update_level_view(audit, record, "level2_fine_grained", fine)
                if high:
                    level1_writer.write(view_record(record, "level1_high_level", high))
                if fine:
                    level2_writer.write(view_record(record, "level2_fine_grained", fine))

    manifest_base = {
        "ontology": ontology,
        "paths": {
            "master_dataset": master_path,
            "level1_high_level": level1_path,
            "level2_fine_grained": level2_path,
        },
    }
    return manifest_base


def label_stats_rows(audit: BuildAudit) -> list[dict[str, Any]]:
    rows = []
    for key in sorted(audit.label_support):
        source, level = key
        support = audit.label_support[key]
        values = list(support.values())
        labels_per = audit.labels_per_record.get(key, [])
        total_assignments = sum(values)
        record_count = len(labels_per)
        largest = max(values) if values else 0
        rare_threshold = 5
        rare_assignments = sum(count for count in values if count < rare_threshold)
        rows.append(
            {
                "source": source,
                "level": level,
                "records": record_count,
                "unique_labels": len(support),
                "total_label_assignments": total_assignments,
                "mean_labels_per_record": round(statistics.mean(labels_per), 4) if labels_per else 0,
                "median_labels_per_record": round(statistics.median(labels_per), 4) if labels_per else 0,
                "single_label_records": sum(value == 1 for value in labels_per),
                "multi_label_records": sum(value > 1 for value in labels_per),
                "proportion_multi_label": round(sum(value > 1 for value in labels_per) / record_count, 6) if record_count else 0,
                "minimum_support": min(values) if values else 0,
                "maximum_support": largest,
                "median_support": round(statistics.median(values), 4) if values else 0,
                "mean_support": round(statistics.mean(values), 4) if values else 0,
                "largest_class_proportion": round(largest / total_assignments, 6) if total_assignments else 0,
                "rare_label_threshold": rare_threshold,
                "rare_label_count": sum(count < rare_threshold for count in values),
                "rare_assignment_proportion": round(rare_assignments / total_assignments, 6) if total_assignments else 0,
                "imbalance_ratio_max_min": round(max(values) / min(values), 4) if values and min(values) else None,
            }
        )
    return rows


def label_distribution_rows(audit: BuildAudit) -> list[dict[str, Any]]:
    rows = []
    for (source, level), counter in sorted(audit.label_support.items()):
        total = sum(counter.values())
        for label, count in counter.most_common():
            rows.append(
                {
                    "source": source,
                    "level": level,
                    "label": label,
                    "support": count,
                    "proportion_of_assignments": round(count / total, 8) if total else 0,
                }
            )
    return rows


def pipeline_stage_rows(audit: BuildAudit) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for source in ("papers_with_code", "bio.tools"):
        raw = audit.raw_counts[source]
        expanded = audit.expanded_counts[source]
        rows.append(
            {
                "stage": "source_to_observation_expansion",
                "source": source,
                "input_records": raw,
                "output_records": expanded,
                "added_by_expansion": max(expanded - raw, 0),
                "removed_records": 0,
                "removal_reason": "not_applicable",
            }
        )
        retained = audit.retained_counts[source]
        removed_total = expanded - retained
        if audit.removal_reasons[source]:
            for reason, count in audit.removal_reasons[source].items():
                rows.append(
                    {
                        "stage": "canonical_master_filter",
                        "source": source,
                        "input_records": expanded,
                        "output_records": retained,
                        "added_by_expansion": 0,
                        "removed_records": count,
                        "removal_reason": reason,
                    }
                )
        else:
            rows.append(
                {
                    "stage": "canonical_master_filter",
                    "source": source,
                    "input_records": expanded,
                    "output_records": retained,
                    "added_by_expansion": 0,
                    "removed_records": removed_total,
                    "removal_reason": "none",
                }
            )
        for level, output_count in [
            ("level1_high_level", audit.level1_counts[source]),
            ("level2_fine_grained", audit.level2_counts[source]),
        ]:
            missing_count = audit.level_filter_reasons.get(f"{source}:{level}", Counter()).get(
                "missing_target_labels_for_level", 0
            )
            rows.append(
                {
                    "stage": f"{level}_view_filter",
                    "source": source,
                    "input_records": retained,
                    "output_records": output_count,
                    "added_by_expansion": 0,
                    "removed_records": missing_count,
                    "removal_reason": "missing_target_labels_for_level" if missing_count else "none",
                }
            )
    return rows


def duplicate_rows(audit: BuildAudit) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    rows.extend(audit.canonical_ids.duplicate_rows("all", "canonical_record_id"))
    for (source, key_type), key_audit in sorted(audit.duplicate_audits.items()):
        rows.extend(key_audit.duplicate_rows(source, key_type))
    return rows


def overlap_rows(audit: BuildAudit) -> list[dict[str, Any]]:
    rows = []
    for key_type, mapping in [
        ("normalized_repository_url", audit.repo_sources),
        ("doi", audit.doi_sources),
        ("normalized_name", audit.name_sources),
    ]:
        for key, sources in mapping.items():
            if len(sources) < 2:
                continue
            strength = "exact" if key_type in {"normalized_repository_url", "doi"} else "ambiguous_name_only"
            rows.append(
                {
                    "key_type": key_type,
                    "key_value": key,
                    "match_strength": strength,
                    "papers_with_code_records": sources.get("papers_with_code", 0),
                    "biotools_records": sources.get("bio.tools", 0),
                    "total_records": sum(sources.values()),
                }
            )
    return sorted(rows, key=lambda row: (row["match_strength"], row["key_type"], -row["total_records"]))


def pwc_mapping_rows(audit: BuildAudit) -> list[dict[str, Any]]:
    rows = []
    for (task, area), count in audit.pwc_task_area_counts.most_common():
        rows.append(
            {
                "pwc_task_label": task,
                "pwc_area_label": area,
                "record_count": count,
                "task_total_records": audit.pwc_task_records[task],
                "area_total_records": audit.pwc_area_records[area],
            }
        )
    return rows


def missingness_rows(audit: BuildAudit) -> list[dict[str, Any]]:
    rows = []
    for source in sorted(audit.rows_by_source):
        total = audit.rows_by_source[source]
        for field_name in MISSINGNESS_FIELDS:
            present = audit.present[(source, field_name)]
            missing_counter = audit.missing[(source, field_name)]
            missing_total = sum(missing_counter.values())
            rows.append(
                {
                    "source": source,
                    "field": field_name,
                    "total_records": total,
                    "present_records": present,
                    "missing_records": missing_total,
                    "present_proportion": round(present / total, 8) if total else 0,
                    "genuinely_absent_in_source": missing_counter.get("genuinely_absent_in_source", 0),
                    "failed_enrichment": missing_counter.get("failed_enrichment", 0),
                    "not_applicable": missing_counter.get("not_applicable", 0),
                    "empty_after_cleaning": missing_counter.get("empty_after_cleaning", 0),
                    "removed_invalid_value": missing_counter.get("removed_invalid_value", 0),
                }
            )
    return rows


def target_leakage_rows() -> list[dict[str, str]]:
    """Classify canonical and legacy fields by modeling role."""

    rows = [
        ("source", "SOURCE_IDENTIFIER", "Stratification/provenance only, not a predictor."),
        ("source_item_id", "SOURCE_IDENTIFIER", "Stable source identifier."),
        ("canonical_record_id", "SOURCE_IDENTIFIER", "Deterministic row identifier."),
        ("repository_url", "SOURCE_IDENTIFIER", "Identifier/provenance, not semantic predictor."),
        ("repository_url_normalized", "SOURCE_IDENTIFIER", "Identifier/provenance, not semantic predictor."),
        ("publication_identifier", "SOURCE_IDENTIFIER", "Identifier/provenance, not semantic predictor."),
        ("doi", "SOURCE_IDENTIFIER", "Identifier/provenance, not semantic predictor."),
        ("paper_title", "SAFE_METADATA", "Publication text; safe unless target labels are embedded in title text by source convention."),
        ("paper_abstract", "SAFE_METADATA", "Publication text; safe textual metadata."),
        ("software_name", "SAFE_METADATA", "Name can contain domain hints; allowed but should be reported separately."),
        ("software_description", "SAFE_METADATA", "Source-provided software description."),
        ("repository_title", "SAFE_METADATA", "Repository text metadata."),
        ("repository_description", "SAFE_METADATA", "Repository text metadata."),
        ("repository_keywords", "SAFE_METADATA", "Repository topics may be user labels; inspect in sensitivity analyses."),
        ("readme_content", "SAFE_METADATA", "README text metadata."),
        ("somef_description", "SAFE_METADATA", "Description extracted from README, not source target hierarchy."),
        ("somef_keywords", "SAFE_METADATA", "README-derived keywords; audit because extraction can echo headings."),
        ("high_level_labels", "TARGET", "Level 1 target."),
        ("fine_grained_labels", "TARGET", "Level 2 target."),
        ("raw_source_labels", "TARGET_DERIVED", "Preserved target provenance."),
        ("raw_source_label_ids", "TARGET_DERIVED", "Preserved target provenance."),
        ("pwc_area_labels", "TARGET", "PwC Level 1 target labels."),
        ("pwc_task_labels", "TARGET", "PwC Level 2 target labels and leakage for PwC Level 1."),
        ("edam_topic_labels", "TARGET", "bio.tools Level 2 target labels and leakage for EDAM Level 1."),
        ("edam_topic_uris", "TARGET", "bio.tools Level 2 target identifiers."),
        ("edam_top_level_labels", "TARGET", "bio.tools Level 1 target labels."),
        ("edam_top_level_uris", "TARGET", "bio.tools Level 1 target identifiers."),
        ("pwc_method_labels", "POTENTIAL_LEAKAGE", "PwC method taxonomy is source classification metadata, not neutral text."),
        ("edam_operation_labels", "POTENTIAL_LEAKAGE", "EDAM operations are ontological annotations and may encode domain."),
        ("labels", "TARGET_DERIVED", "Legacy ambiguous target field, not safe as predictor."),
        ("secondary_labels", "POTENTIAL_LEAKAGE", "Legacy source classification metadata."),
        ("tasks", "POTENTIAL_LEAKAGE", "Legacy field is a Level 2 target for PwC and operation labels for bio.tools."),
        ("methods", "POTENTIAL_LEAKAGE", "Legacy source taxonomy metadata."),
    ]
    return [{"field": field_name, "classification": classification, "rationale": rationale} for field_name, classification, rationale in rows]


def write_machine_tables(paths: BuildPaths, audit: BuildAudit) -> dict[str, Path]:
    table_paths = {
        "pipeline_stage_accounting": paths.tables_dir / "pipeline_stage_accounting.csv",
        "duplicate_keys": paths.tables_dir / "duplicate_keys.csv",
        "cross_source_overlaps": paths.tables_dir / "cross_source_overlaps.csv",
        "pwc_task_area_mapping": paths.tables_dir / "pwc_task_area_mapping.csv",
        "label_granularity_stats": paths.tables_dir / "label_granularity_stats.csv",
        "label_distribution": paths.tables_dir / "label_distribution.csv",
        "missing_data_by_source": paths.tables_dir / "missing_data_by_source.csv",
        "target_leakage_field_classification": paths.tables_dir / "target_leakage_field_classification.csv",
        "unit_of_analysis_counts": paths.tables_dir / "unit_of_analysis_counts.csv",
        "external_enrichment_summary": paths.tables_dir / "external_enrichment_summary.csv",
    }
    write_csv_rows(table_paths["pipeline_stage_accounting"], pipeline_stage_rows(audit))
    write_csv_rows(table_paths["duplicate_keys"], duplicate_rows(audit))
    write_csv_rows(table_paths["cross_source_overlaps"], overlap_rows(audit))
    write_csv_rows(table_paths["pwc_task_area_mapping"], pwc_mapping_rows(audit))
    write_csv_rows(table_paths["label_granularity_stats"], label_stats_rows(audit))
    write_csv_rows(table_paths["label_distribution"], label_distribution_rows(audit))
    write_csv_rows(table_paths["missing_data_by_source"], missingness_rows(audit))
    write_csv_rows(table_paths["target_leakage_field_classification"], target_leakage_rows())
    write_csv_rows(table_paths["unit_of_analysis_counts"], unit_of_analysis_rows(audit))
    write_csv_rows(table_paths["external_enrichment_summary"], enrichment_summary_rows(audit))
    return table_paths


def unit_of_analysis_rows(audit: BuildAudit) -> list[dict[str, Any]]:
    rows = []
    for source in ("papers_with_code", "bio.tools"):
        rows.append({"source": source, "count_type": "source_records", "count": audit.raw_counts[source]})
        rows.append({"source": source, "count_type": "expanded_observations", "count": audit.expanded_counts[source]})
        rows.append({"source": source, "count_type": "retained_master_records", "count": audit.retained_counts[source]})
        rows.append({"source": source, "count_type": "level1_records", "count": audit.level1_counts[source]})
        rows.append({"source": source, "count_type": "level2_records", "count": audit.level2_counts[source]})
        rows.append(
            {
                "source": source,
                "count_type": "unique_normalized_repositories_observed",
                "count": sum(1 for _, counts in audit.repo_sources.items() if counts.get(source)),
            }
        )
        rows.append(
            {
                "source": source,
                "count_type": "unique_dois_observed",
                "count": sum(1 for _, counts in audit.doi_sources.items() if counts.get(source)),
            }
        )
        rows.append(
            {
                "source": source,
                "count_type": "unique_normalized_names_observed",
                "count": sum(1 for _, counts in audit.name_sources.items() if counts.get(source)),
            }
        )
        for size, count in sorted(audit.repository_count_distribution[source].items()):
            rows.append(
                {
                    "source": source,
                    "count_type": "source_records_by_repository_count",
                    "count_subtype": size,
                    "count": count,
                }
            )
        for size, count in sorted(audit.source_publication_distribution[source].items()):
            rows.append(
                {
                    "source": source,
                    "count_type": "source_records_by_publication_expansion_count",
                    "count_subtype": size,
                    "count": count,
                }
            )
    return rows


def enrichment_summary_rows(audit: BuildAudit) -> list[dict[str, Any]]:
    rows = []
    for family, counter in [
        ("openalex", audit.openalex_stats),
        ("github_artifacts", audit.github_artifact_stats),
        ("somef", audit.somef_stats),
    ]:
        for metric, value in counter.most_common():
            rows.append({"enrichment_source": family, "metric": metric, "value": value})
    rows.append({"enrichment_source": "somef", "metric": "configured_threshold", "value": config.SOMEF_THRESHOLD})
    return rows


def counter_markdown(counter: Mapping[Any, int], limit: int = 12) -> str:
    rows = [{"value": key, "count": value} for key, value in Counter(counter).most_common(limit)]
    return markdown_table(rows) if rows else "No rows."


def markdown_table(rows: list[Mapping[str, Any]], limit: int | None = None) -> str:
    if limit is not None:
        rows = rows[:limit]
    if not rows:
        return "No rows."
    columns = list(rows[0].keys())
    lines = [
        "| " + " | ".join(columns) + " |",
        "| " + " | ".join("---" for _ in columns) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(str(row.get(column, "")) for column in columns) + " |")
    return "\n".join(lines)


def write_report(path: Path, title: str, body: str) -> None:
    atomic_write_text(path, f"# {title}\n\n{body.strip()}\n")


def write_audit_reports(paths: BuildPaths, audit: BuildAudit, ontology: EdamOntology) -> None:
    overlap = overlap_rows(audit)
    duplicate = duplicate_rows(audit)
    label_stats = label_stats_rows(audit)

    unit_body = f"""
## Recommendation

Use the canonical master row as a source observation with stable provenance, not
as a silently deduplicated software package. For PwC, one row represents one
PwC paper/source record with all known repository URLs preserved. For bio.tools,
one row represents one tool-publication observation when DOI information exists,
and one tool observation when it does not. This mismatch is scientifically
important and remains marked for human review before any final experiment.

## Core Counts

{markdown_table(unit_of_analysis_rows(audit), limit=40)}

## Bio.tools DOI Expansion

bio.tools raw tool rows can expand when multiple DOI values are attached to one
software entry. Expanded rows preserve the same software metadata and differ by
publication identifier. This is evidence of a possible dependence structure,
not a deduplication instruction.

Publication expansion distribution:

{counter_markdown(audit.source_publication_distribution["bio.tools"])}

## Repository Multiplicity

PwC records may reference zero, one, or multiple repositories. The canonical
record preserves the full normalized repository list and uses the first
normalized GitHub URL as the primary repository for model-ready views.

PwC repository count distribution:

{counter_markdown(audit.repository_count_distribution["papers_with_code"])}
"""
    write_report(paths.reports_dir / "UNIT_OF_ANALYSIS_AUDIT.md", "Unit Of Analysis Audit", unit_body)

    overlap_body = f"""
## Cross-Source Overlap

Strong overlaps are based on normalized repository URL or DOI. Name-only matches
are diagnostics and must not be treated as exact duplicates without manual
review.

{markdown_table(overlap, limit=50)}

## Duplicate Keys

Duplicate identifiers and repeated repositories/publications are expected in
some places because source observations are not identical to software packages.
They are reported here rather than removed.

{markdown_table(duplicate, limit=80)}
"""
    write_report(paths.reports_dir / "DATASET_OVERLAP_AUDIT.md", "Dataset Overlap Audit", overlap_body)

    filter_body = f"""
## Filters Applied In The Candidate Master Build

The candidate master build applies only two record-level filters:

1. require a normalized GitHub repository URL;
2. require at least one target label at either Level 1 or Level 2.

It does not require a DOI for bio.tools. That older asymmetric rule is reported
as a scientific concern because it can bias bio.tools toward tools with formal
publication metadata.

## Accounting Table

{markdown_table(pipeline_stage_rows(audit), limit=40)}

## Source-Specific Label Cleanup

PwC `General` broad labels are removed from Level 1 targets but preserved in
`pwc_area_labels` and `raw_source_labels`.

- PwC records containing `General`: {audit.pwc_generic_label_record_count}
- PwC `General` assignments: {audit.pwc_generic_label_assignment_count}

## Bias Notes

The GitHub requirement is applied to both sources, but its impact is not
necessarily symmetric: PwC is paper-centered and bio.tools is software-centered.
Missing publication metadata is retained as missingness rather than becoming a
master-dataset exclusion.
"""
    write_report(paths.reports_dir / "FILTERING_AUDIT.md", "Filtering Audit", filter_body)

    task_to_areas: dict[str, set[str]] = defaultdict(set)
    for task, area in audit.pwc_task_area_counts:
        task_to_areas[task].add(area)
    multi_area_tasks = {task: areas for task, areas in task_to_areas.items() if len(areas) > 1}
    pwc_body = f"""
## Summary

- Unique PwC high-level areas observed: {len(audit.pwc_area_records)}
- Unique PwC task labels observed: {len(audit.pwc_task_records)}
- Records with multiple areas: {audit.pwc_multi_area_records}
- Records with multiple tasks: {audit.pwc_multi_task_records}
- Tasks associated with multiple areas: {len(multi_area_tasks)}
- Task labels found on records without an area: {len(audit.pwc_tasks_without_area)}
- Areas found on records without a task: {len(audit.pwc_areas_without_task)}

## Determinism

The task-to-area relationship is not assumed to be deterministic. A task is
reported under every area with which it co-occurs in the frozen source data.

## Most Frequent Task-Area Pairs

{markdown_table(pwc_mapping_rows(audit), limit=40)}
"""
    write_report(paths.reports_dir / "PWC_LABEL_HIERARCHY.md", "PwC Label Hierarchy", pwc_body)

    multi_mapping_topics = count_multi_mapping_topics(paths.mappings_dir / "edam_detailed_to_high_level.csv")
    edam_body = f"""
## Frozen Ontology

- Local path: `{ontology.path}`
- SHA256: `{ontology.sha256}`
- Version: {ontology.version}
- Metadata: {json.dumps(ontology.metadata, ensure_ascii=False, sort_keys=True)}
- EDAM active topic concepts parsed: {len(ontology.labels)}
- EDAM root topic ids found: {", ".join(sorted(ontology.root_topics)) or "none"}

## Mapping Summary

- Original distinct EDAM topic labels observed: {len(audit.edam_raw_topic_support)}
- Resulting distinct high-level EDAM labels observed: {len(audit.edam_high_topic_support)}
- Records with multiple mapped high-level EDAM labels: {audit.edam_record_multi_parent_count}
- Detailed EDAM topics with multiple high-level mappings in ontology table: {multi_mapping_topics}

Mapping statuses observed in retained or filtered observations:

{counter_markdown(audit.edam_mapping_status)}

## High-Level Support

{counter_markdown(audit.edam_high_topic_support, limit=30)}
"""
    write_report(paths.reports_dir / "EDAM_HIERARCHY_AUDIT.md", "EDAM Hierarchy Audit", edam_body)

    granularity_body = f"""
## Label-Space Comparison

The comparison is based on hierarchy role, multi-label behavior, support, and
imbalance. Similar label counts are not treated as evidence of comparability.

{markdown_table(label_stats, limit=20)}

## Scientific Interpretation

Level 1 compares PwC broad collection areas with the highest meaningful EDAM
Topic categories below the generic Topic root. This is the more defensible
granularity-aligned comparison, subject to human review of the EDAM DAG
multi-parent cases.

Level 2 compares PwC tasks with original EDAM topics. These are both more
detailed source annotation spaces, but they are not guaranteed to be
scientifically equivalent: EDAM topics are ontology concepts, while PwC tasks
are task taxonomy entries. Treat Level 2 as requiring review before any
paper-level claim of comparability.
"""
    write_report(paths.reports_dir / "LABEL_GRANULARITY_COMPARISON.md", "Label Granularity Comparison", granularity_body)

    leakage_body = f"""
## Field Classification

Target-derived fields are preserved for provenance, but they must not be used
as predictors when they determine the target level.

{markdown_table(target_leakage_rows(), limit=None)}

## Critical Safeguards

- Do not use PwC task labels as predictors for PwC Level 1 classification.
- Do not use original EDAM topic labels or URIs as predictors for EDAM Level 1 classification.
- Do not use legacy `labels`, `tasks`, `secondary_labels`, or `methods` as generic text predictors.
- Keep identifiers out of model text features.
"""
    write_report(paths.reports_dir / "TARGET_LEAKAGE_AUDIT.md", "Target Leakage Audit", leakage_body)

    enrichment_body = f"""
## Summary

No external data was recollected. This audit inspects saved local caches and
artifacts only.

{markdown_table(enrichment_summary_rows(audit), limit=80)}

## OpenAlex

Requested DOI values are checked against returned OpenAlex DOI values where
available. Mismatches are counted in the machine-readable table.

## GitHub And README Artifacts

Saved repository artifact folders are counted, including README presence and
metadata JSON validity. Redirects and repository renames are not recoverable
without network calls unless already present in saved metadata.

## SoMEF

Saved SoMEF JSON files and manifest statuses are counted. The configured
threshold in the repository is `{config.SOMEF_THRESHOLD}`. Exact SoMEF package
version is reported as unknown unless captured in local artifacts.
"""
    write_report(paths.reports_dir / "EXTERNAL_ENRICHMENT_AUDIT.md", "External Enrichment Audit", enrichment_body)

    missing_body = f"""
## Missingness By Source

Missingness is calculated on the retained canonical master records and split by
source. Reasons distinguish not-applicable fields, source absence, failed
enrichment, and empty-after-cleaning cases.

{markdown_table(missingness_rows(audit), limit=80)}
"""
    write_report(paths.reports_dir / "MISSING_DATA_AUDIT.md", "Missing Data Audit", missing_body)

    validation_body = scientific_validation_body(audit, ontology, label_stats)
    write_report(paths.reports_dir / "DATASET_SCIENTIFIC_VALIDATION.md", "Dataset Scientific Validation", validation_body)


def count_multi_mapping_topics(path: Path) -> int:
    if not path.exists():
        return 0
    by_topic: dict[str, set[str]] = defaultdict(set)
    with path.open("r", encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            topic = row.get("detailed_topic_uri") or ""
            high = row.get("high_level_topic_uri") or ""
            if high:
                by_topic[topic].add(high)
    return sum(len(values) > 1 for values in by_topic.values())


def scientific_validation_body(audit: BuildAudit, ontology: EdamOntology, label_stats: list[dict[str, Any]]) -> str:
    canonical_duplicate_ids = [
        key for key, count in audit.canonical_ids.counts.items() if count > 1
    ]
    if canonical_duplicate_ids:
        audit.blocking_issues.append(f"Duplicate canonical_record_id values: {len(canonical_duplicate_ids)}")
    if not ontology.root_topics:
        audit.blocking_issues.append("No EDAM Topic root was identified in the frozen ontology.")

    audit.review_issues.extend(
        [
            "Confirm whether the canonical source-observation unit is acceptable for final experiments.",
            "Review bio.tools DOI expansion before treating expanded rows as independent observations.",
            "Review PwC task-to-area non-determinism before using hierarchical claims.",
            "Review EDAM multi-parent mappings because EDAM is a DAG, not a tree.",
            "Confirm that Level 2 PwC tasks and EDAM topics are comparable enough for the intended analysis.",
        ]
    )
    status_rows = []
    for issue in audit.blocking_issues:
        status_rows.append({"concern": issue, "status": "BLOCKING"})
    for issue in audit.review_issues:
        status_rows.append({"concern": issue, "status": "REQUIRES_REVIEW"})
    if not status_rows:
        status_rows.append({"concern": "No blocking validation issues detected by automated checks.", "status": "RESOLVED"})

    return f"""
## Dataset Identity

The build creates a candidate canonical master dataset plus Level 1 and Level 2
analysis-ready views from frozen local inputs. It is not a final immutable
release until human review approves the scientific decisions.

## Unit Of Analysis

PwC rows represent source paper records. bio.tools rows represent tool
observations, expanded to tool-publication observations where DOI values exist.

## Source Provenance

PwC input: `{config.PWC_MERGED_JSONL}`.
bio.tools input: `{config.BIOTOOLS_FLAT_CSV}` plus `{config.BIOTOOLS_RAW_JSONL}`.
EDAM ontology: `{ontology.path}` with SHA256 `{ontology.sha256}`.

## Record Counts

{markdown_table(unit_of_analysis_rows(audit), limit=40)}

## Filtering

{markdown_table(pipeline_stage_rows(audit), limit=40)}

## Duplicates And Cross-Source Overlap

Duplicate and overlap evidence is written to machine-readable tables. No
within-source or cross-source duplicates are removed automatically.

## Missingness

Missingness is documented in `reports/MISSING_DATA_AUDIT.md` and
`reports/tables/missing_data_by_source.csv`.

## Enrichment Failures

Saved OpenAlex, README/GitHub, and SoMEF artifacts are audited without
recollection.

## PwC Hierarchy

PwC area-task relationships are reconstructed from co-occurrence in the frozen
source data. They are not invented when ambiguous.

## EDAM Hierarchy

EDAM mappings preserve multiple high-level ancestors when the ontology DAG
supports them.

## Label Granularity

{markdown_table(label_stats, limit=20)}

## Leakage Risks

Target-derived fields are preserved but classified as unsafe predictors where
they determine the target.

## Remaining Scientific Concerns

{markdown_table(status_rows)}
"""


def dependency_versions() -> dict[str, str]:
    packages = ["pandas", "requests", "tqdm", "pyarrow", "scikit-learn", "numpy", "scipy"]
    versions = {}
    for package in packages:
        try:
            versions[package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            versions[package] = "not_installed"
    return versions


def git_commit() -> str:
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=config.BASE_DIR,
            check=True,
            capture_output=True,
            text=True,
        )
        return completed.stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def write_release_readme(paths: BuildPaths, audit: BuildAudit, ontology: EdamOntology) -> None:
    readme = f"""
# Candidate Paper V1 Dataset

## 1. Purpose

This candidate dataset represents research software metadata from Papers with
Code and bio.tools for scientific review before final experiments.

## 2. Sources

- Papers with Code: local frozen file `{paths.pwc_merged_jsonl}`. Acquisition
  date/version: unknown.
- bio.tools: local frozen files `{paths.biotools_flat_csv}` and
  `{paths.biotools_raw_jsonl}`. Acquisition date/version: unknown.
- EDAM: local frozen ontology `{paths.edam_owl}`. Version: {ontology.version}.

## 3. Unit Of Analysis

PwC records are source paper records with repository URLs preserved. bio.tools
records are tool observations, expanded to tool-publication observations when
multiple DOI values exist. This remains a review item before final freeze.

## 4. Inclusion/Exclusion Criteria

The canonical master candidate retains records with a normalized GitHub
repository URL and at least one usable Level 1 or Level 2 label. A DOI is not
required for bio.tools in this candidate build. Removed records are accounted
for in `reports/tables/pipeline_stage_accounting.csv`.

## 5. Dataset Construction

Frozen local sources -> source-specific parsing -> deterministic identifiers ->
PwC Level 1/Level 2 label assignment and EDAM DAG mapping -> GitHub/README/SoMEF
cache merge -> master record filter -> Level 1 and Level 2 derived views ->
audit reports -> manifest.

## 6. Level 1 Classification

PwC uses broad area labels from `main_collection_areas`. bio.tools uses EDAM
Topic ancestors immediately below the generic EDAM Topic root, preserving
multi-parent mappings.

## 7. Level 2 Classification

PwC uses task labels from the frozen source category data. bio.tools uses the
original detailed EDAM topic annotations. Comparability at this level requires
human scientific review.

## 8. Hierarchical Mapping

PwC task-area relationships are reconstructed from source co-occurrence. EDAM
is handled as a DAG; mappings are written to
`data/mappings/edam_detailed_to_high_level.csv`.

## 9. Multi-Label Behavior

List-valued label fields are stored as JSON lists. Derived views include
`target_labels`, `is_single_label`, and `is_multi_label`.

## 10. Duplicate/Overlap Handling

Duplicates and cross-source overlaps are reported but not removed automatically.

## 11. Missing Data

Missing values are not collapsed into one empty-string category. Missingness by
reason is reported in `reports/tables/missing_data_by_source.csv`.

## 12. External Enrichment

OpenAlex, GitHub/README, and SoMEF data are read from saved local caches only.
The build performs no network calls.

## 13. Potential Biases

The GitHub repository requirement may select for software with public GitHub
implementations. Publication metadata coverage differs by source.

## 14. Target Leakage Safeguards

Do not use target-derived fields as predictors. In particular, PwC task labels
must not predict PwC broad areas, and original EDAM topics must not predict EDAM
high-level labels.

## 15. Schema

Canonical fields are documented in the manifest and include source identifiers,
metadata, source-specific labels, both classification levels, enrichment
provenance, and deterministic IDs.

## 16. Record Counts

- PwC retained master records: {audit.retained_counts["papers_with_code"]}
- bio.tools retained master records: {audit.retained_counts["bio.tools"]}
- PwC Level 1 records: {audit.level1_counts["papers_with_code"]}
- bio.tools Level 1 records: {audit.level1_counts["bio.tools"]}
- PwC Level 2 records: {audit.level2_counts["papers_with_code"]}
- bio.tools Level 2 records: {audit.level2_counts["bio.tools"]}

## 17. Reproduction

```bash
poetry run python scripts/build_final_dataset.py
```

## 18. Integrity

Checksums for frozen inputs and outputs are stored in `MANIFEST.json`.

## 19. Limitations

This is a candidate build pending human review. It should not be used for final
experiments until unresolved concerns in
`reports/DATASET_SCIENTIFIC_VALIDATION.md` have been reviewed.
"""
    atomic_write_text(paths.release_dir / "README.md", readme.strip() + "\n")


def write_manifest(paths: BuildPaths, audit: BuildAudit, ontology: EdamOntology) -> dict[str, Any]:
    input_paths = [
        paths.pwc_merged_jsonl,
        paths.biotools_flat_csv,
        paths.biotools_raw_jsonl,
        paths.edam_owl,
        paths.openalex_cache_jsonl,
        paths.somef_manifest_jsonl,
    ]
    frozen_inputs = []
    for path in input_paths:
        frozen_inputs.append(
            {
                "path": str(path),
                "exists": path.exists(),
                "size_bytes": path.stat().st_size if path.exists() else None,
                "sha256": sha256_file(path) if path.exists() else None,
            }
        )

    output_paths = [
        paths.release_dir / "master_dataset.jsonl",
        paths.release_dir / "level1_high_level.jsonl",
        paths.release_dir / "level2_fine_grained.jsonl",
        paths.release_dir / "README.md",
        paths.mappings_dir / "edam_detailed_to_high_level.csv",
    ]
    outputs = []
    for path in output_paths:
        outputs.append(
            {
                "path": str(path),
                "exists": path.exists(),
                "size_bytes": path.stat().st_size if path.exists() else None,
                "sha256": sha256_file(path) if path.exists() else None,
            }
        )

    manifest = {
        "dataset_release_identifier": "paper_v1_candidate",
        "release_status": "human_review_required",
        "git_commit": git_commit(),
        "python_version": sys.version,
        "platform": platform.platform(),
        "dependency_versions": dependency_versions(),
        "frozen_input_files": frozen_inputs,
        "edam": {
            "version": ontology.version,
            "sha256": ontology.sha256,
            "metadata": ontology.metadata,
            "path": str(ontology.path),
        },
        "external_enrichment_cache_checksums": {
            "openalex_cache_jsonl": next(
                (item for item in frozen_inputs if item["path"] == str(paths.openalex_cache_jsonl)), {}
            ),
            "somef_run_manifest_jsonl": next(
                (item for item in frozen_inputs if item["path"] == str(paths.somef_manifest_jsonl)), {}
            ),
            "repository_artifact_directories": audit.github_artifact_stats.get("artifact_directories", 0),
        },
        "transformation_stages": pipeline_stage_rows(audit),
        "filtering_counts": {source: dict(counter) for source, counter in audit.removal_reasons.items()},
        "expansion_counts": dict(audit.expansion_added),
        "hierarchy_definitions": {
            "pwc": "Broad labels from main_collection_areas; fine labels from PwC tasks.",
            "edam": "Detailed EDAM topics mapped through frozen EDAM DAG to Topic-root children.",
        },
        "unique_label_counts": {
            f"{source}:{level}": len(counter)
            for (source, level), counter in audit.label_support.items()
        },
        "output_record_counts": {
            "master_dataset": sum(audit.retained_counts.values()),
            "level1_high_level": sum(audit.level1_counts.values()),
            "level2_fine_grained": sum(audit.level2_counts.values()),
        },
        "outputs": outputs,
        "blocking_issues": audit.blocking_issues,
        "review_issues": audit.review_issues,
    }
    atomic_write_text(paths.release_dir / "MANIFEST.json", json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    return manifest


def write_top_level_readme_note() -> None:
    """Append a concise canonical-build note to README if it is absent."""

    readme_path = config.BASE_DIR / "README.md"
    marker = "## Canonical Dataset Finalization"
    text = readme_path.read_text(encoding="utf-8")
    if marker in text:
        return
    note = f"""

{marker}

The audit-first offline build command for the candidate canonical paper dataset is:

```bash
poetry run python scripts/build_final_dataset.py
```

It reads only frozen local inputs and makes no network calls. Deterministic
record IDs are SHA-256 based hashes of stable source semantics:

- PwC: source, source item, publication URL, and normalized repository URL.
- bio.tools: source, bio.tools ID, DOI when present, and normalized repository URL.

The generated `data/final/paper_v1/` files are candidate review artifacts. They
must not be treated as experiment-ready until
`reports/DATASET_SCIENTIFIC_VALIDATION.md` has no blocking issues and the
scientific review has approved the remaining review items.
"""
    atomic_write_text(readme_path, text.rstrip() + note)


def validate_accounting(audit: BuildAudit) -> None:
    for source in ("papers_with_code", "bio.tools"):
        expanded = audit.expanded_counts[source]
        retained = audit.retained_counts[source]
        removed = sum(audit.removal_reasons[source].values())
        if expanded != retained + removed:
            audit.blocking_issues.append(
                f"Accounting mismatch for {source}: expanded={expanded}, retained={retained}, removed={removed}"
            )
        level1_missing = audit.level_filter_reasons.get(f"{source}:level1_high_level", Counter()).get(
            "missing_target_labels_for_level", 0
        )
        if retained != audit.level1_counts[source] + level1_missing:
            audit.blocking_issues.append(f"Level 1 accounting mismatch for {source}")
        level2_missing = audit.level_filter_reasons.get(f"{source}:level2_fine_grained", Counter()).get(
            "missing_target_labels_for_level", 0
        )
        if retained != audit.level2_counts[source] + level2_missing:
            audit.blocking_issues.append(f"Level 2 accounting mismatch for {source}")


def run_build(paths: BuildPaths | None = None) -> dict[str, Any]:
    paths = paths or BuildPaths()
    audit = BuildAudit()
    build_result = build_datasets(paths, audit)
    ontology: EdamOntology = build_result["ontology"]
    validate_accounting(audit)
    table_paths = write_machine_tables(paths, audit)
    write_audit_reports(paths, audit, ontology)
    write_release_readme(paths, audit, ontology)
    manifest = write_manifest(paths, audit, ontology)
    return {"manifest": manifest, "tables": table_paths, "audit": audit}


def main() -> None:
    result = run_build()
    manifest = result["manifest"]
    print(json.dumps({
        "release_status": manifest["release_status"],
        "git_commit": manifest["git_commit"],
        "output_record_counts": manifest["output_record_counts"],
        "blocking_issues": manifest["blocking_issues"],
        "review_issue_count": len(manifest["review_issues"]),
    }, indent=2, sort_keys=True))
    if manifest["blocking_issues"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
