#!/usr/bin/env python3
"""Map bio.tools EDAM topic labels to top-level EDAM topic categories.

The early machine-learning experiments need a stable, interpretable target
space. bio.tools records can contain EDAM topics from different hierarchy
depths, so training directly on those detailed labels would mix broad and
specific concepts. This script maps every EDAM topic to the highest meaningful
topic category below the EDAM ``Topic`` root and removes generic catch-all
labels before writing analysis-ready datasets.
"""
from __future__ import annotations

import logging
import re
import sys
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict, deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import requests

try:
    from tqdm import tqdm
except ImportError:  # pragma: no cover
    def tqdm(iterable, **_: object):
        return iterable

sys.path.append(str(Path(__file__).resolve().parent.parent))

from src import config
from src.utils.io_utils import configure_logging, read_csv_dicts, read_jsonl, write_csv, write_jsonl
from src.utils.text_utils import clean_list


BASE_DIR = Path(__file__).resolve().parent.parent
EDAM_URL = "https://edamontology.org/EDAM.owl"
EDAM_DIR = BASE_DIR / "data" / "raw" / "edam"
EDAM_OWL_PATH = EDAM_DIR / "EDAM.owl"

REQUESTED_INPUT_JSONL = BASE_DIR / "data" / "final_analysis" / "biotools_aligned.jsonl"
FALLBACK_INPUT_JSONL = config.BIOTOOLS_ALIGNED_JSONL
BIOTOOLS_FLAT_CSV = config.BIOTOOLS_FLAT_CSV

OUTPUT_DIR = BASE_DIR / "data" / "final_analysis"
OUTPUT_JSONL = OUTPUT_DIR / "biotools_aligned_top_level_labels.jsonl"
OUTPUT_CSV = OUTPUT_DIR / "biotools_aligned_top_level_labels.csv"

RESULTS_DIR = BASE_DIR / "results" / "label_harmonization"
RAW_LABEL_DISTRIBUTION_CSV = RESULTS_DIR / "raw_label_distribution.csv"
TOP_LEVEL_LABEL_DISTRIBUTION_CSV = RESULTS_DIR / "top_level_label_distribution.csv"
LABEL_MAPPING_TABLE_CSV = RESULTS_DIR / "label_mapping_table.csv"
UNMAPPED_LABELS_CSV = RESULTS_DIR / "unmapped_labels.csv"
EXCLUDED_GENERIC_LABELS_CSV = RESULTS_DIR / "excluded_generic_labels.csv"
SUMMARY_XLSX = RESULTS_DIR / "biotools_edam_mapping_summary.xlsx"
REPORT_PATH = RESULTS_DIR / "BIOTOOLS_EDAM_TOP_LEVEL_MAPPING_REPORT.md"
LOG_PATH = RESULTS_DIR / "biotools_edam_top_level_mapping.log"

GENERIC_LABELS = {"topic", "general", "other", "miscellaneous", "unknown"}
ADMIN_LABEL_PATTERNS = ("obsolete", "deprecated")
RDF_RESOURCE = "{http://www.w3.org/1999/02/22-rdf-syntax-ns#}resource"
RDF_ABOUT = "{http://www.w3.org/1999/02/22-rdf-syntax-ns#}about"
OWL_DEPRECATED = "{http://www.w3.org/2002/07/owl#}deprecated"
OWL_CLASS = "{http://www.w3.org/2002/07/owl#}Class"
OWL_ONTOLOGY = "{http://www.w3.org/2002/07/owl#}Ontology"
OWL_VERSION_INFO = "{http://www.w3.org/2002/07/owl#}versionInfo"
OWL_VERSION_IRI = "{http://www.w3.org/2002/07/owl#}versionIRI"
DOAP_VERSION = "{http://usefulinc.com/ns/doap#}Version"
OBO_LEGACY_DATE = "{http://purl.obolibrary.org/obo/}date"
RDFS_LABEL = "{http://www.w3.org/2000/01/rdf-schema#}label"
RDFS_SUBCLASS_OF = "{http://www.w3.org/2000/01/rdf-schema#}subClassOf"
TOPIC_ID_PATTERN = re.compile(r"(topic_\d+)")

LOGGER = logging.getLogger("map_biotools_edam_to_top_level")


def configure_script_logging() -> None:
    """Configure console and file logs for reproducible execution."""
    configure_logging()
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    root_logger = logging.getLogger()
    if not any(isinstance(handler, logging.FileHandler) and handler.baseFilename == str(LOG_PATH) for handler in root_logger.handlers):
        file_handler = logging.FileHandler(LOG_PATH, encoding="utf-8")
        file_handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
        )
        root_logger.addHandler(file_handler)


def now_utc() -> str:
    """Return a reproducible ISO timestamp for reports and logs."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def topic_id(value: Any) -> str | None:
    """Extract an EDAM ``topic_0000`` identifier from a URI or plain id."""
    if not value:
        return None
    match = TOPIC_ID_PATTERN.search(str(value))
    return match.group(1) if match else None


def canonical_topic_uri(topic: str | None) -> str | None:
    """Represent topic ids as stable EDAM HTTPS URIs in output datasets."""
    return f"https://edamontology.org/{topic}" if topic else None


def is_generic_or_admin_label(label: str | None) -> bool:
    """Return True for labels that should not become training targets."""
    normalized = (label or "").strip().casefold()
    if not normalized or normalized in GENERIC_LABELS:
        return True
    return any(pattern in normalized for pattern in ADMIN_LABEL_PATTERNS)


def ensure_edam_ontology() -> tuple[Path, str | None]:
    """Download EDAM.owl once and then reuse the cached ontology file.

    The script intentionally caches the ontology under ``data/raw/edam`` so
    later runs use the same file unless the researcher deliberately removes or
    replaces it. This keeps the mapping reproducible while still allowing the
    first run to acquire the latest EDAM ontology automatically.
    """
    EDAM_DIR.mkdir(parents=True, exist_ok=True)
    if EDAM_OWL_PATH.exists():
        LOGGER.info("Using cached EDAM ontology at %s", EDAM_OWL_PATH)
        cached_at = datetime.fromtimestamp(EDAM_OWL_PATH.stat().st_mtime, timezone.utc)
        return EDAM_OWL_PATH, cached_at.replace(microsecond=0).isoformat()

    LOGGER.info("Downloading EDAM ontology from %s", EDAM_URL)
    download_started_at = now_utc()
    response = requests.get(EDAM_URL, stream=True, timeout=60)
    response.raise_for_status()
    total_bytes = int(response.headers.get("content-length") or 0)
    progress = tqdm(total=total_bytes, unit="B", unit_scale=True, desc="Downloading EDAM.owl")
    tmp_path = EDAM_OWL_PATH.with_suffix(".owl.tmp")
    with tmp_path.open("wb") as handle:
        for chunk in response.iter_content(chunk_size=1024 * 256):
            if not chunk:
                continue
            handle.write(chunk)
            progress.update(len(chunk))
    progress.close()
    tmp_path.replace(EDAM_OWL_PATH)
    LOGGER.info("Cached EDAM ontology at %s", EDAM_OWL_PATH)
    return EDAM_OWL_PATH, download_started_at


def ontology_version(root: ET.Element) -> str:
    """Extract a human-readable EDAM version from OWL metadata."""
    ontology = root.find(f".//{OWL_ONTOLOGY}")
    if ontology is None:
        return "unknown"
    version_info = ontology.findtext(OWL_VERSION_INFO)
    if version_info:
        return version_info.strip()
    version_iri = ontology.attrib.get(OWL_VERSION_IRI)
    if version_iri:
        return version_iri
    doap_version = ontology.findtext(DOAP_VERSION)
    ontology_date = ontology.findtext(OBO_LEGACY_DATE)
    if doap_version and ontology_date:
        return f"{doap_version.strip()} ({ontology_date.strip()})"
    if doap_version:
        return doap_version.strip()
    if ontology_date:
        return ontology_date.strip()
    return "unknown"


def parse_bool(text: str | None) -> bool:
    """Interpret OWL boolean-ish text."""
    return (text or "").strip().casefold() in {"true", "1"}


def parse_edam_topics(path: Path) -> dict[str, Any]:
    """Parse EDAM topic concepts and their parent relationships from OWL.

    Only classes whose identifiers begin with ``topic_`` are retained. Parent
    links are filtered the same way, because the ML target mapping should stay
    inside the EDAM Topic branch and not climb into broader ontology machinery.
    """
    tree = ET.parse(path)
    root = tree.getroot()
    labels: dict[str, str] = {}
    parents: dict[str, set[str]] = defaultdict(set)
    deprecated: set[str] = set()

    for klass in root.findall(f".//{OWL_CLASS}"):
        current_topic = topic_id(klass.attrib.get(RDF_ABOUT))
        if not current_topic:
            continue
        label = klass.findtext(RDFS_LABEL)
        labels[current_topic] = (label or current_topic).strip()
        if parse_bool(klass.findtext(OWL_DEPRECATED)):
            deprecated.add(current_topic)
        for parent in klass.findall(RDFS_SUBCLASS_OF):
            parent_topic = topic_id(parent.attrib.get(RDF_RESOURCE))
            if parent_topic:
                parents[current_topic].add(parent_topic)

    active_topics = {
        topic
        for topic, label in labels.items()
        if topic not in deprecated and not any(pattern in label.casefold() for pattern in ADMIN_LABEL_PATTERNS)
    }
    filtered_parents = {
        topic: {parent for parent in parents.get(topic, set()) if parent in active_topics}
        for topic in active_topics
    }
    child_counts = Counter(parent for parent_set in filtered_parents.values() for parent in parent_set)
    return {
        "version": ontology_version(root),
        "labels": {topic: labels[topic] for topic in active_topics},
        "parents": filtered_parents,
        "child_counts": child_counts,
    }


def top_level_topics_for(topic: str, labels: dict[str, str], parents: dict[str, set[str]]) -> set[str]:
    """Find highest meaningful EDAM topic ancestors below the ``Topic`` root.

    EDAM is a directed acyclic graph rather than a strict tree, so a detailed
    topic can legitimately resolve to more than one top-level category. The
    traversal walks upward through parent links and keeps the last useful node
    before reaching ``Topic`` or another generic/admin node. Generic ancestors
    are excluded because labels like ``Topic`` or ``General`` are too broad for
    supervised ML experiments and would add noise rather than signal.
    """
    if topic not in labels:
        return set()

    results: set[str] = set()
    queue: deque[tuple[str, tuple[str, ...]]] = deque([(topic, (topic,))])
    visited_paths: set[tuple[str, tuple[str, ...]]] = set()

    while queue:
        current, path = queue.popleft()
        state = (current, path)
        if state in visited_paths:
            continue
        visited_paths.add(state)

        usable_parents = [
            parent
            for parent in parents.get(current, set())
            if parent in labels and not is_generic_or_admin_label(labels.get(parent))
        ]
        if not usable_parents:
            if not is_generic_or_admin_label(labels.get(current)):
                results.add(current)
            continue
        for parent in sorted(usable_parents):
            if parent not in path:
                queue.append((parent, (*path, parent)))

    return results


def build_topic_mapping(ontology: dict[str, Any]) -> pd.DataFrame:
    """Create one mapping row per EDAM topic concept."""
    labels: dict[str, str] = ontology["labels"]
    parents: dict[str, set[str]] = ontology["parents"]
    rows = []
    for source_topic in sorted(labels):
        top_topics = sorted(top_level_topics_for(source_topic, labels, parents), key=lambda item: labels[item].casefold())
        rows.append(
            {
                "raw_label_uri": canonical_topic_uri(source_topic),
                "raw_label": labels[source_topic],
                "top_level_label_uris": [canonical_topic_uri(topic) for topic in top_topics],
                "top_level_labels": [labels[topic] for topic in top_topics],
                "parent_uris": [canonical_topic_uri(parent) for parent in sorted(parents.get(source_topic, set()))],
                "parent_labels": [labels[parent] for parent in sorted(parents.get(source_topic, set()))],
                "mapping_success": bool(top_topics),
                "mapping_notes": "mapped" if top_topics else "no_top_level_topic_found",
            }
        )
    return pd.DataFrame(rows)


def split_pipe(value: Any) -> list[str]:
    """Split pipe-delimited bio.tools CSV fields."""
    if value is None:
        return []
    if isinstance(value, list):
        return clean_list(value)
    return [part.strip() for part in str(value).split("|") if part.strip()]


def base_biotools_id(item_id: Any) -> str | None:
    """Remove DOI expansion suffixes so aligned records can join raw CSV rows."""
    if not item_id:
        return None
    return str(item_id).split("::doi::", maxsplit=1)[0]


def load_raw_topic_lookup() -> dict[str, dict[str, list[str]]]:
    """Load original bio.tools topic labels and URIs from the flattened source."""
    lookup: dict[str, dict[str, list[str]]] = {}
    if not BIOTOOLS_FLAT_CSV.exists():
        LOGGER.warning("Missing flat bio.tools CSV with topic URIs: %s", BIOTOOLS_FLAT_CSV)
        return lookup
    for row in read_csv_dicts(BIOTOOLS_FLAT_CSV):
        biotools_id = row.get("biotools_id")
        if not biotools_id:
            continue
        lookup[biotools_id] = {
            "raw_labels": split_pipe(row.get("topic_terms")),
            "raw_label_uris": split_pipe(row.get("topic_uris")),
        }
    LOGGER.info("Loaded raw EDAM topic URI lookup for %s bio.tools records", f"{len(lookup):,}")
    return lookup


def ensure_requested_input() -> Path:
    """Use the requested input path, creating it from the current aligned file if needed."""
    if REQUESTED_INPUT_JSONL.exists():
        return REQUESTED_INPUT_JSONL
    if not FALLBACK_INPUT_JSONL.exists():
        raise FileNotFoundError(f"Neither {REQUESTED_INPUT_JSONL} nor {FALLBACK_INPUT_JSONL} exists")
    REQUESTED_INPUT_JSONL.parent.mkdir(parents=True, exist_ok=True)
    records = list(read_jsonl(FALLBACK_INPUT_JSONL))
    write_jsonl(records, REQUESTED_INPUT_JSONL)
    LOGGER.warning("Created requested input %s from fallback %s", REQUESTED_INPUT_JSONL, FALLBACK_INPUT_JSONL)
    return REQUESTED_INPUT_JSONL


def raw_topics_for_record(
    record: dict[str, Any],
    raw_lookup: dict[str, dict[str, list[str]]],
    label_to_topics: dict[str, list[str]],
) -> tuple[list[str], list[str]]:
    """Recover raw EDAM labels and URIs for one aligned bio.tools record."""
    lookup_row = raw_lookup.get(base_biotools_id(record.get("item_id")) or "")
    raw_labels = clean_list((lookup_row or {}).get("raw_labels") or record.get("raw_labels") or record.get("labels"))
    raw_uris = clean_list((lookup_row or {}).get("raw_label_uris") or record.get("raw_label_uris") or record.get("label_uris"))
    if raw_uris:
        return raw_labels, raw_uris

    inferred_topics: list[str] = []
    for label in raw_labels:
        inferred_topics.extend(label_to_topics.get(label.casefold(), []))
    inferred_topics = list(dict.fromkeys(inferred_topics))
    return raw_labels, [canonical_topic_uri(topic) for topic in inferred_topics if canonical_topic_uri(topic)]


def map_records(
    records: list[dict[str, Any]],
    ontology: dict[str, Any],
    label_mapping_table: pd.DataFrame,
    raw_lookup: dict[str, dict[str, list[str]]],
) -> tuple[list[dict[str, Any]], pd.DataFrame, pd.DataFrame]:
    """Map each record's raw EDAM topics to top-level training labels."""
    labels: dict[str, str] = ontology["labels"]
    label_to_topics: dict[str, list[str]] = defaultdict(list)
    for topic, label in labels.items():
        label_to_topics[label.casefold()].append(topic)

    mapping_by_topic = {
        topic_id(row["raw_label_uri"]): row
        for _, row in label_mapping_table.iterrows()
        if topic_id(row["raw_label_uri"])
    }
    mapped_records: list[dict[str, Any]] = []
    unmapped_counter: Counter[tuple[str, str]] = Counter()
    excluded_counter: Counter[tuple[str, str]] = Counter()

    for record in tqdm(records, desc="Mapping bio.tools EDAM labels"):
        raw_labels, raw_label_uris = raw_topics_for_record(record, raw_lookup, label_to_topics)
        mapped_labels: list[str] = []
        mapped_uris: list[str] = []
        notes: list[str] = []

        raw_pairs = list(zip(raw_labels, raw_label_uris))
        if not raw_pairs and raw_labels:
            raw_pairs = [(label, "") for label in raw_labels]

        for raw_label, raw_uri in raw_pairs:
            raw_topic = topic_id(raw_uri)
            if not raw_topic:
                candidates = label_to_topics.get(raw_label.casefold(), [])
                raw_topic = candidates[0] if len(candidates) == 1 else None
            if not raw_topic or raw_topic not in mapping_by_topic:
                unmapped_counter[(raw_label, raw_uri)] += 1
                notes.append(f"unmapped:{raw_label or raw_uri}")
                continue

            row = mapping_by_topic[raw_topic]
            for top_label, top_uri in zip(row["top_level_labels"], row["top_level_label_uris"]):
                if is_generic_or_admin_label(top_label):
                    excluded_counter[(top_label, top_uri)] += 1
                    continue
                mapped_labels.append(top_label)
                mapped_uris.append(top_uri)

        deduped = {
            label: uri
            for label, uri in sorted(
                zip(mapped_labels, mapped_uris),
                key=lambda pair: (str(pair[0]).casefold(), str(pair[1])),
            )
        }
        output_record = dict(record)
        output_record["raw_labels"] = raw_labels
        output_record["raw_label_uris"] = raw_label_uris
        output_record["labels"] = list(deduped)
        output_record["label_uris"] = list(deduped.values())
        output_record["label_level_used"] = "edam_top_level"
        output_record["edam_mapping_success"] = bool(deduped)
        output_record["edam_mapping_notes"] = "; ".join(notes) if notes else "mapped"
        mapped_records.append(output_record)

    unmapped_columns = ["raw_label", "raw_label_uri", "record_count"]
    excluded_columns = ["excluded_label", "excluded_label_uri", "excluded_count", "removed_reason"]
    unmapped = pd.DataFrame(
        [
            {"raw_label": label, "raw_label_uri": uri, "record_count": count}
            for (label, uri), count in unmapped_counter.most_common()
        ],
        columns=unmapped_columns,
    )
    excluded = pd.DataFrame(
        [
            {"excluded_label": label, "excluded_label_uri": uri, "excluded_count": count, "removed_reason": "excluded_generic_label"}
            for (label, uri), count in excluded_counter.most_common()
        ],
        columns=excluded_columns,
    )
    return mapped_records, unmapped, excluded


def counter_table(counter: Counter, value_name: str) -> pd.DataFrame:
    """Convert a Counter to a distribution table."""
    total = sum(counter.values())
    return pd.DataFrame(
        [
            {value_name: value, "count": count, "percent": (count / total * 100) if total else 0.0}
            for value, count in counter.most_common()
        ]
    )


def label_counter(records: list[dict[str, Any]], field: str) -> Counter:
    """Count list-like labels from mapped records."""
    counter: Counter = Counter()
    for record in records:
        counter.update(clean_list(record.get(field)))
    return counter


def write_tables(tables: dict[str, pd.DataFrame]) -> None:
    """Write CSV quality tables and a multi-sheet Excel workbook."""
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    tables["raw_label_distribution"].to_csv(RAW_LABEL_DISTRIBUTION_CSV, index=False)
    tables["top_level_label_distribution"].to_csv(TOP_LEVEL_LABEL_DISTRIBUTION_CSV, index=False)
    tables["label_mapping_table"].to_csv(LABEL_MAPPING_TABLE_CSV, index=False)
    tables["unmapped_labels"].to_csv(UNMAPPED_LABELS_CSV, index=False)
    tables["excluded_generic_labels"].to_csv(EXCLUDED_GENERIC_LABELS_CSV, index=False)
    with pd.ExcelWriter(SUMMARY_XLSX) as writer:
        for name, table in tables.items():
            table.to_excel(writer, sheet_name=name[:31], index=False)


def dataframe_to_markdown(table: pd.DataFrame) -> str:
    """Render a small Markdown table without optional dependencies."""
    if table.empty:
        return "No rows."
    columns = list(table.columns)
    rows = table.astype(str).values.tolist()
    return "\n".join(
        [
            "| " + " | ".join(columns) + " |",
            "| " + " | ".join("---" for _ in columns) + " |",
            *["| " + " | ".join(row) + " |" for row in rows],
        ]
    )


def write_report(tables: dict[str, pd.DataFrame], ontology: dict[str, Any], download_date: str | None, mapped_records: list[dict[str, Any]]) -> None:
    """Write a Markdown report documenting the mapping run."""
    summary = {row["metric"]: row["value"] for _, row in tables["summary"].iterrows()}
    final_distribution = tables["top_level_label_distribution"].copy()
    if not final_distribution.empty:
        final_distribution["percent"] = final_distribution["percent"].map(lambda value: f"{value:.2f}")

    report = f"""# bio.tools EDAM Top-Level Mapping Report

This report was generated for the early subset analysis and uses only top-level EDAM topic labels.

## Summary

- Ontology version used: {ontology["version"]}
- Download/cache date: {download_date or "unknown"}
- Ontology file path: `{EDAM_OWL_PATH}`
- Number of EDAM topic concepts: {summary.get("edam_topic_concepts", 0)}
- Number of unique original labels: {summary.get("unique_original_labels", 0)}
- Number of unique top-level labels: {summary.get("unique_top_level_labels", 0)}
- Records successfully mapped: {summary.get("records_successfully_mapped", 0)}
- Records not mapped: {summary.get("records_not_mapped", 0)}
- Labels excluded: {summary.get("labels_excluded", 0)}

## Method

bio.tools records may contain EDAM topic labels at multiple hierarchy depths. For early ML experiments, this script preserves the original labels in `raw_labels` and `raw_label_uris`, traverses the EDAM parent graph upward, and replaces `labels` and `label_uris` with the highest meaningful EDAM topic categories below the ontology root. Generic labels such as Topic, General, Other, Miscellaneous, and Unknown are removed because they are not useful supervised targets.

## Final label distribution

{dataframe_to_markdown(final_distribution)}

## Outputs

- Mapped JSONL: `{OUTPUT_JSONL}`
- Mapped CSV: `{OUTPUT_CSV}`
- Quality tables: `{RESULTS_DIR}`
- Excel workbook: `{SUMMARY_XLSX}`
"""
    REPORT_PATH.write_text(report, encoding="utf-8")


def main() -> None:
    configure_script_logging()
    LOGGER.info("Starting bio.tools EDAM top-level label mapping")
    ontology_path, download_date = ensure_edam_ontology()
    ontology = parse_edam_topics(ontology_path)
    LOGGER.info("Parsed %s active EDAM topic concepts", f"{len(ontology['labels']):,}")

    input_path = ensure_requested_input()
    raw_records = list(read_jsonl(input_path))
    raw_lookup = load_raw_topic_lookup()
    label_mapping_table = build_topic_mapping(ontology)
    mapped_records, unmapped_labels, excluded_generic_labels = map_records(
        raw_records, ontology, label_mapping_table, raw_lookup
    )

    raw_distribution = counter_table(label_counter(mapped_records, "raw_labels"), "raw_label")
    top_distribution = counter_table(label_counter(mapped_records, "labels"), "top_level_label")
    summary = pd.DataFrame(
        [
            {"metric": "ontology_version", "value": ontology["version"]},
            {"metric": "download_date", "value": download_date or "unknown"},
            {"metric": "ontology_file_path", "value": str(ontology_path)},
            {"metric": "edam_topic_concepts", "value": len(ontology["labels"])},
            {"metric": "records_total", "value": len(mapped_records)},
            {"metric": "unique_original_labels", "value": len(raw_distribution)},
            {"metric": "unique_top_level_labels", "value": len(top_distribution)},
            {"metric": "records_successfully_mapped", "value": sum(bool(record["edam_mapping_success"]) for record in mapped_records)},
            {"metric": "records_not_mapped", "value": sum(not bool(record["edam_mapping_success"]) for record in mapped_records)},
            {"metric": "labels_excluded", "value": int(excluded_generic_labels["excluded_count"].sum()) if not excluded_generic_labels.empty else 0},
        ]
    )

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    write_jsonl(mapped_records, OUTPUT_JSONL)
    write_csv(mapped_records, OUTPUT_CSV)
    tables = {
        "summary": summary,
        "raw_label_distribution": raw_distribution,
        "top_level_label_distribution": top_distribution,
        "label_mapping_table": label_mapping_table,
        "unmapped_labels": unmapped_labels,
        "excluded_generic_labels": excluded_generic_labels,
    }
    write_tables(tables)
    write_report(tables, ontology, download_date, mapped_records)

    LOGGER.info("Wrote mapped datasets to %s and %s", OUTPUT_JSONL, OUTPUT_CSV)
    LOGGER.info("Top-level EDAM label distribution:\n%s", top_distribution.to_string(index=False))
    if not unmapped_labels.empty:
        LOGGER.warning("Unmapped labels:\n%s", unmapped_labels.head(25).to_string(index=False))

    print("\nFinal top-level label distribution:")
    print(top_distribution.to_string(index=False))
    if unmapped_labels.empty:
        print("\nMapping failures: none")
    else:
        print("\nMapping failures:")
        print(unmapped_labels.to_string(index=False))


if __name__ == "__main__":
    main()
