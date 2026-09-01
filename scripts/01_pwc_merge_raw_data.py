from pathlib import Path
import json
import re
from datetime import date, datetime

import numpy as np
import pandas as pd
from tqdm import tqdm


# ============================================================
# Paths
# ============================================================

BASE_DIR = Path(__file__).resolve().parent.parent

RAW_PWC_DIR = BASE_DIR / "data" / "orig_pow_archive"
OUTPUT_DIR = BASE_DIR / "data" / "pwc_merged"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

PAPER_FILES = [
    RAW_PWC_DIR / "papers-with-abstracts-1.parquet",
    RAW_PWC_DIR / "papers-with-abstracts-2.parquet",
    RAW_PWC_DIR / "papers-with-abstracts-3.parquet",
    RAW_PWC_DIR / "papers-with-abstracts-4.parquet",
]

LINKS_FILE = RAW_PWC_DIR / "links-between-paper-and-code.parquet"

OUTPUT_JSONL = OUTPUT_DIR / "pwc_merged_relevant_attributes.jsonl"
OUTPUT_CSV = OUTPUT_DIR / "pwc_merged_relevant_attributes.csv"


# ============================================================
# Logging
# ============================================================

def log(message):
    print(f"[INFO] {message}", flush=True)


def log_section(title):
    print("\n" + "=" * 70, flush=True)
    print(title, flush=True)
    print("=" * 70, flush=True)


# ============================================================
# Helpers
# ============================================================

def normalize_title(title):
    if title is None:
        return None

    try:
        if pd.isna(title):
            return None
    except Exception:
        pass

    title = str(title).lower().strip()
    title = re.sub(r"\s+", " ", title)
    title = re.sub(r"[^\w\s\-]", "", title)
    return title


def normalize_url(url):
    if url is None:
        return None

    try:
        if pd.isna(url):
            return None
    except Exception:
        pass

    return str(url).strip().rstrip("/")


def make_json_serializable(obj):
    if isinstance(obj, (pd.Timestamp, datetime, date)):
        return obj.isoformat()

    if isinstance(obj, np.ndarray):
        return obj.tolist()

    if isinstance(obj, np.integer):
        return int(obj)

    if isinstance(obj, np.floating):
        return float(obj)

    if isinstance(obj, np.bool_):
        return bool(obj)

    try:
        if pd.isna(obj):
            return None
    except Exception:
        pass

    return str(obj)


def safe_list(value):
    if value is None:
        return []

    try:
        if pd.isna(value):
            return []
    except Exception:
        pass

    if isinstance(value, list):
        return value

    if isinstance(value, tuple):
        return list(value)

    if isinstance(value, np.ndarray):
        return value.tolist()

    if isinstance(value, str):
        if not value.strip():
            return []

        try:
            parsed = json.loads(value)
            if isinstance(parsed, list):
                return parsed
            return [parsed]
        except Exception:
            return [value]

    return [value]


def unique_clean(values):
    cleaned = []

    for value in values:
        if value is None:
            continue

        try:
            if pd.isna(value):
                continue
        except Exception:
            pass

        value = str(value).strip()

        if value and value not in cleaned:
            cleaned.append(value)

    return cleaned


# ============================================================
# Extraction
# ============================================================

def extract_task_names(tasks):
    names = []

    for task in safe_list(tasks):
        if isinstance(task, dict):
            name = (
                task.get("task")
                or task.get("name")
                or task.get("title")
            )
            if name:
                names.append(name)
        elif isinstance(task, str):
            names.append(task)

    return unique_clean(names)


def extract_methods(methods):
    records = []
    areas = []
    collections = []

    for method in safe_list(methods):
        if not isinstance(method, dict):
            continue

        main_collection = method.get("main_collection") or {}

        if not isinstance(main_collection, dict):
            main_collection = {}

        area = main_collection.get("area")
        collection_name = main_collection.get("name")
        collection_parent = main_collection.get("parent")

        if area:
            areas.append(area)

        if collection_name:
            collections.append(collection_name)

        records.append(
            {
                "method": method.get("name"),
                "method_full_name": method.get("full_name"),
                "method_url": method.get("source_url"),
                "source_title": method.get("source_title"),
                "source_url": method.get("source_url"),
                "introduced_year": method.get("introduced_year"),
                "main_collection_area": area,
                "main_collection_name": collection_name,
                "main_collection_parent": collection_parent,
            }
        )

    return {
        "methods": records,
        "collections": unique_clean(collections),
        "main_collection_areas": unique_clean(areas),
    }


# ============================================================
# Load data
# ============================================================

def load_papers():
    log_section("LOADING PAPERS")

    dfs = []

    for file in PAPER_FILES:
        log(f"Reading {file}")
        df = pd.read_parquet(file)
        log(f"Loaded {len(df):,} rows")
        dfs.append(df)

    papers = pd.concat(dfs, ignore_index=True)

    log(f"Total raw papers: {len(papers):,}")
    log(f"Paper columns: {list(papers.columns)}")

    papers["paper_key"] = papers["title"].apply(normalize_title)

    before = len(papers)
    papers = papers.dropna(subset=["paper_key"])
    log(f"Dropped missing paper_key: {before - len(papers):,}")

    before = len(papers)
    papers = papers.drop_duplicates(subset=["paper_key"])
    log(f"Dropped duplicate paper titles: {before - len(papers):,}")

    log(f"Final papers: {len(papers):,}")

    task_non_empty = papers["tasks"].apply(lambda x: len(safe_list(x)) > 0).sum()
    method_non_empty = papers["methods"].apply(lambda x: len(safe_list(x)) > 0).sum()

    log(f"Papers with raw tasks: {task_non_empty:,}")
    log(f"Papers with raw methods: {method_non_empty:,}")

    sample_methods = papers["methods"].dropna()
    if len(sample_methods) > 0:
        log("Example methods value:")
        print(sample_methods.iloc[0], flush=True)

    return papers


def load_links():
    log_section("LOADING REPOSITORY LINKS")

    log(f"Reading {LINKS_FILE}")
    links = pd.read_parquet(LINKS_FILE)

    log(f"Raw links: {len(links):,}")
    log(f"Links columns: {list(links.columns)}")

    links["paper_key"] = links["paper_title"].apply(normalize_title)
    links["repo_url"] = links["repo_url"].apply(normalize_url)

    before = len(links)
    links = links.dropna(subset=["paper_key", "repo_url"])
    log(f"Dropped links missing paper_key/repo_url: {before - len(links):,}")

    before = len(links)
    links = links.drop_duplicates()
    log(f"Dropped duplicate links: {before - len(links):,}")

    log(f"Final links: {len(links):,}")
    log(f"Unique linked papers: {links['paper_key'].nunique():,}")
    log(f"Unique repositories: {links['repo_url'].nunique():,}")

    return links


# ============================================================
# Aggregation
# ============================================================

def aggregate_links(links):
    log_section("AGGREGATING LINKS")

    grouped = {}

    for paper_key, group in tqdm(
        links.groupby("paper_key"),
        total=links["paper_key"].nunique(),
        desc="Aggregating repository links",
    ):
        repo_urls = unique_clean(group["repo_url"].tolist())

        repository_links = []

        for _, row in group.iterrows():
            repository_links.append(
                {
                    "repo_url": row.get("repo_url"),
                    "is_official": row.get("is_official"),
                    "mentioned_in_paper": row.get("mentioned_in_paper"),
                    "mentioned_in_github": row.get("mentioned_in_github"),
                    "framework": row.get("framework"),
                }
            )

        grouped[paper_key] = {
            "github_repo": repo_urls[0] if repo_urls else None,
            "github_repos": repo_urls,
            "repository_links": repository_links,
        }

    log(f"Aggregated link records: {len(grouped):,}")

    return grouped


# ============================================================
# Merge
# ============================================================

def build_merged_dataset():
    papers = load_papers()
    links = load_links()
    links_by_paper = aggregate_links(links)

    log_section("MERGING DATASET")
    log(f"Papers to process: {len(papers):,}")

    records = []

    with_github = 0
    with_tasks = 0
    with_methods = 0
    with_area = 0
    with_title = 0
    with_abstract = 0

    for _, paper in tqdm(
        papers.iterrows(),
        total=len(papers),
        desc="Merging papers",
    ):
        paper_key = paper["paper_key"]

        repo_data = links_by_paper.get(
            paper_key,
            {
                "github_repo": None,
                "github_repos": [],
                "repository_links": [],
            },
        )

        task_names = extract_task_names(paper.get("tasks"))
        method_data = extract_methods(paper.get("methods"))
        main_collection_areas = method_data["main_collection_areas"]

        paper_title = paper.get("title")
        abstract = paper.get("abstract")

        if paper_title:
            with_title += 1

        if abstract:
            with_abstract += 1

        if repo_data["github_repo"]:
            with_github += 1

        if task_names:
            with_tasks += 1

        if method_data["methods"]:
            with_methods += 1

        if main_collection_areas:
            with_area += 1

        record = {
            "paper_title": paper_title,
            "abstract": abstract,
            "short_abstract": paper.get("short_abstract"),

            "paper_url": paper.get("paper_url"),
            "url_abs": paper.get("url_abs"),
            "url_pdf": paper.get("url_pdf"),
            "arxiv_id": paper.get("arxiv_id"),
            "conference": paper.get("conference"),
            "date": paper.get("date"),

            "github_repo": repo_data["github_repo"],
            "github_repos": repo_data["github_repos"],
            "repository_links": repo_data["repository_links"],

            "main_collection_area": (
                main_collection_areas[0]
                if len(main_collection_areas) == 1
                else None
            ),
            "main_collection_areas": main_collection_areas,

            "papers with code categories": {
                "tasks": task_names,
                "methods": method_data["methods"],
                "collections": method_data["collections"],
                "main_collection_areas": main_collection_areas,
            },

            "num_repositories": len(repo_data["github_repos"]),
            "num_tasks": len(task_names),
            "num_methods": len(method_data["methods"]),
            "num_collections": len(method_data["collections"]),
            "num_main_collection_areas": len(main_collection_areas),
        }

        records.append(record)

    log_section("MERGE COVERAGE")
    log(f"Number of records: {len(records):,}")
    log(f"With paper title: {with_title:,}")
    log(f"With abstract: {with_abstract:,}")
    log(f"With GitHub repo: {with_github:,}")
    log(f"With tasks: {with_tasks:,}")
    log(f"With methods: {with_methods:,}")
    log(f"With main collection area: {with_area:,}")

    return records


# ============================================================
# Save
# ============================================================

def save_outputs(records):
    log_section("SAVING JSON")
    log(f"Writing {len(records):,} records to {OUTPUT_JSONL}")

    with open(OUTPUT_JSONL, "w", encoding="utf-8") as f:
        for record in tqdm(records, desc="Writing JSONL"):
            f.write(
                json.dumps(
                    record,
                    ensure_ascii=False,
                    default=make_json_serializable,
                )
                + "\n"
            )

    log("JSON saved")

    log_section("BUILDING CSV")

    rows = []

    for record in tqdm(records, desc="Building CSV rows"):
        categories = record["papers with code categories"]

        rows.append(
            {
                "paper_title": record["paper_title"],
                "abstract": record["abstract"],
                "short_abstract": record["short_abstract"],
                "paper_url": record["paper_url"],
                "url_abs": record["url_abs"],
                "url_pdf": record["url_pdf"],
                "arxiv_id": record["arxiv_id"],
                "conference": record["conference"],
                "date": record["date"],
                "github_repo": record["github_repo"],
                "github_repos": json.dumps(
                    record["github_repos"],
                    ensure_ascii=False,
                    default=make_json_serializable,
                ),
                "main_collection_area": record["main_collection_area"],
                "main_collection_areas": json.dumps(
                    record["main_collection_areas"],
                    ensure_ascii=False,
                    default=make_json_serializable,
                ),
                "tasks": json.dumps(
                    categories["tasks"],
                    ensure_ascii=False,
                    default=make_json_serializable,
                ),
                "methods": json.dumps(
                    categories["methods"],
                    ensure_ascii=False,
                    default=make_json_serializable,
                ),
                "collections": json.dumps(
                    categories["collections"],
                    ensure_ascii=False,
                    default=make_json_serializable,
                ),
                "num_repositories": record["num_repositories"],
                "num_tasks": record["num_tasks"],
                "num_methods": record["num_methods"],
                "num_collections": record["num_collections"],
                "num_main_collection_areas": record["num_main_collection_areas"],
            }
        )

    log(f"CSV rows built: {len(rows):,}")

    df = pd.DataFrame(rows)
    df.to_csv(OUTPUT_CSV, index=False)

    log(f"CSV saved to {OUTPUT_CSV}")

    log_section("FINAL COVERAGE")

    log(f"Number of records: {len(records):,}")
    log(f"With GitHub repo: {sum(1 for r in records if r['github_repo']):,}")
    log(f"With main collection area: {sum(1 for r in records if r['main_collection_areas']):,}")
    log(f"With tasks: {sum(1 for r in records if r['papers with code categories']['tasks']):,}")
    log(f"With methods: {sum(1 for r in records if r['papers with code categories']['methods']):,}")
    log(f"With paper title: {sum(1 for r in records if r['paper_title']):,}")
    log(f"With abstract: {sum(1 for r in records if r['abstract']):,}")

    log(f"Saved JSON to: {OUTPUT_JSON}")
    log(f"Saved CSV to:  {OUTPUT_CSV}")


# ============================================================
# Main
# ============================================================

def main():
    records = build_merged_dataset()
    save_outputs(records)


if __name__ == "__main__":
    main()