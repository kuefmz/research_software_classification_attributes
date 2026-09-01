from pathlib import Path
import json
import hashlib

import pandas as pd
from tqdm import tqdm


# ============================================================
# Paths
# ============================================================

BASE_DIR = Path(__file__).resolve().parent.parent

INPUT_JSONL = (
    BASE_DIR
    / "data"
    / "pwc_merged"
    / "pwc_merged_relevant_attributes.jsonl"
)

OUTPUT_DIR = BASE_DIR / "data" / "pwc_filtered_structured"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

OUTPUT_JSON = OUTPUT_DIR / "papers_with_code_aligned.json"
OUTPUT_CSV = OUTPUT_DIR / "papers_with_code_aligned.csv"


# ============================================================
# Helpers
# ============================================================

def log(message: str) -> None:
    print(f"[INFO] {message}", flush=True)


def make_id(source: str, title: str | None, publication_url: str | None) -> str:
    raw = f"{source}|{title or ''}|{publication_url or ''}"
    return hashlib.md5(raw.encode("utf-8")).hexdigest()


def clean_text(value):
    if value is None:
        return None

    if isinstance(value, float) and pd.isna(value):
        return None

    text = str(value).strip()

    if not text or text.lower() == "nan":
        return None

    return text


def clean_list(values):
    if not values:
        return []

    cleaned = []

    for value in values:
        if value is None:
            continue

        if isinstance(value, float) and pd.isna(value):
            continue

        value = str(value).strip()

        if value and value.lower() != "nan" and value not in cleaned:
            cleaned.append(value)

    return cleaned


def get_publication_url(record):
    return (
        clean_text(record.get("url_abs"))
        or clean_text(record.get("paper_url"))
        or clean_text(record.get("url_pdf"))
    )


def get_methods(record):
    categories = record.get("papers with code categories", {})
    raw_methods = categories.get("methods", [])

    methods = []

    for method in raw_methods:
        if isinstance(method, dict):
            name = (
                method.get("method")
                or method.get("method_full_name")
            )
            if name:
                methods.append(name)
        elif isinstance(method, str):
            methods.append(method)

    return clean_list(methods)


def get_secondary_labels(record):
    categories = record.get("papers with code categories", {})
    return clean_list(categories.get("collections", []))


def get_tasks(record):
    categories = record.get("papers with code categories", {})
    return clean_list(categories.get("tasks", []))


def get_labels(record):
    labels = record.get("main_collection_areas", [])

    if not labels:
        categories = record.get("papers with code categories", {})
        labels = categories.get("main_collection_areas", [])

    return clean_list(labels)


def align_record(record):
    source = "papers_with_code"

    paper_title = clean_text(record.get("paper_title"))
    paper_abstract = clean_text(record.get("abstract"))
    publication_url = get_publication_url(record)

    repository_urls = clean_list(record.get("github_repos", []))
    repository_url = (
        clean_text(record.get("github_repo"))
        or (repository_urls[0] if repository_urls else None)
    )

    labels = get_labels(record)
    secondary_labels = get_secondary_labels(record)
    tasks = get_tasks(record)
    methods = get_methods(record)

    item_id = make_id(source, paper_title, publication_url)

    return {
        "source": source,
        # "item_id": item_id,

        # software-level fields
        "software_name": None,
        "software_description": None,

        # publication-level fields
        "paper_title": paper_title,
        "paper_abstract": paper_abstract,
        "publication_url": publication_url,

        # repository-level fields
        # "repository_url": repository_url,
        "repository_urls": repository_urls,

        # classification fields
        "labels": labels,
        # "label_scheme": "papers_with_code_main_collection_area",
        "secondary_labels": secondary_labels,
        # "secondary_label_scheme": "papers_with_code_collection",
        "tasks": tasks,
        # "task_scheme": "papers_with_code_task",
        "methods": methods,
        # "method_scheme": "papers_with_code_method",

        # # useful filtering flags
        # "has_publication": bool(paper_title or paper_abstract or publication_url),
        # "has_repository": bool(repository_url),
        # "has_labels": bool(labels),
        # "has_single_label": len(labels) == 1,
        # "has_multiple_labels": len(labels) > 1,
        # "has_tasks": bool(tasks),
        # "has_methods": bool(methods),

        # # counts
        # "num_repository_urls": len(repository_urls),
        # "num_labels": len(labels),
        # "num_secondary_labels": len(secondary_labels),
        # "num_tasks": len(tasks),
        # "num_methods": len(methods),
    }


def save_json(records, path):
    log(f"Writing JSON: {path}")

    with open(path, "w", encoding="utf-8") as f:
        json.dump(records, f, indent=2, ensure_ascii=False)

    log("JSON saved")


def save_csv(records, path):
    log(f"Writing CSV: {path}")

    rows = []

    for record in tqdm(records, desc="Building CSV"):
        rows.append(
            {
                "source": record["source"],
                "item_id": record["item_id"],
                "software_name": record["software_name"],
                "software_description": record["software_description"],
                "paper_title": record["paper_title"],
                "paper_abstract": record["paper_abstract"],
                "publication_url": record["publication_url"],
                "repository_url": record["repository_url"],
                "repository_urls": json.dumps(record["repository_urls"], ensure_ascii=False),
                "labels": json.dumps(record["labels"], ensure_ascii=False),
                "secondary_labels": json.dumps(record["secondary_labels"], ensure_ascii=False),
                "tasks": json.dumps(record["tasks"], ensure_ascii=False),
                "methods": json.dumps(record["methods"], ensure_ascii=False),
            }
        )

    pd.DataFrame(rows).to_csv(path, index=False)

    log("CSV saved")


def print_coverage(records):
    log("")
    log("Coverage:")
    log(f"Total records: {len(records):,}")
    log(f"With repository: {sum(bool(r['repository_url']) for r in records):,}")
    log(f"With labels: {sum(bool(r['labels']) for r in records):,}")
    log(f"Single-label: {sum(len(r['labels']) == 1 for r in records):,}")
    log(f"Multi-label: {sum(len(r['labels']) > 1 for r in records):,}")
    log(f"With tasks: {sum(bool(r['tasks']) for r in records):,}")
    log(f"With methods: {sum(bool(r['methods']) for r in records):,}")


def main():
    log(f"Reading merged PwC data: {INPUT_JSONL}")

    raw_records = []

    with open(INPUT_JSONL, "r", encoding="utf-8") as f:
        for line in tqdm(f, desc="Reading JSONL"):
            if line.strip():
                raw_records.append(json.loads(line))

    log(f"Loaded raw records: {len(raw_records):,}")

    aligned_records = []

    for record in tqdm(raw_records, desc="Aligning records"):
        aligned_records.append(align_record(record))

    print_coverage(aligned_records)

    save_json(aligned_records, OUTPUT_JSON)
    save_csv(aligned_records, OUTPUT_CSV)

    log("")
    log(f"Done.")
    log(f"JSON: {OUTPUT_JSON}")
    log(f"CSV:  {OUTPUT_CSV}")


if __name__ == "__main__":
    main()