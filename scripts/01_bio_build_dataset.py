#!/usr/bin/env python3
"""Build bio.tools datasets aligned with the software-attribute paper methodology.

Outputs:
- biotools_raw.jsonl
- biotools_flat_all.csv
- biotools_multilabel.csv
- biotools_singlelabel.csv
- biotools_dataset_summary.csv

The script keeps one row per bio.tools entry. Labels are EDAM topic terms.
Repository attributes are extracted from bio.tools link/download/documentation/homepage fields.
Publication metadata is represented by DOI/PMID/PMCID and optional publication note/metadata when present.
Abstracts are not generally available in bio.tools; use DOI/PMID export to enrich abstracts later
(e.g., Crossref/OpenAlex/EuropePMC), then re-run notebooks with the enriched column.
"""
from __future__ import annotations

import argparse, json, re, time
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

import pandas as pd
import requests
from tqdm import tqdm

API_BASE = "https://bio.tools/api/t/?format=json"
GITHUB_RE = re.compile(r"https?://(?:www\.)?github\.com/([^/\s]+)/([^/#?\s]+)", re.I)


def normalise_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        return " ".join(normalise_text(v) for v in value if v is not None)
    if isinstance(value, dict):
        return " ".join(normalise_text(v) for v in value.values())
    return re.sub(r"\s+", " ", str(value)).strip()


def github_url_from_tool(tool: dict[str, Any]) -> str:
    candidates: list[str] = []
    for field in ["homepage", "link", "download", "documentation"]:
        value = tool.get(field)
        if isinstance(value, str):
            candidates.append(value)
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, dict) and item.get("url"):
                    candidates.append(str(item["url"]))
    for url in candidates:
        m = GITHUB_RE.search(url)
        if m:
            owner, repo = m.group(1), m.group(2).replace(".git", "")
            return f"https://github.com/{owner}/{repo}"
    return ""


def readme_url_from_github(repo_url: str) -> str:
    m = GITHUB_RE.search(repo_url or "")
    if not m:
        return ""
    owner, repo = m.group(1), m.group(2).replace(".git", "")
    # raw.githubusercontent default branch heuristic; notebook can still use empty if 404
    return f"https://raw.githubusercontent.com/{owner}/{repo}/HEAD/README.md"


def fetch_readme(repo_url: str, timeout: int = 20) -> str:
    raw = readme_url_from_github(repo_url)
    if not raw:
        return ""
    try:
        r = requests.get(raw, timeout=timeout, headers={"User-Agent": "research-software-attribute-study"})
        if r.status_code == 200 and len(r.text) > 20:
            return r.text[:20000]
    except requests.RequestException:
        return ""
    return ""


def safe_json_response(r: requests.Response) -> dict[str, Any] | None:
    try:
        return r.json()
    except requests.exceptions.JSONDecodeError:
        print("\nNon-JSON response received.")
        print(f"URL: {r.url}")
        print(f"Status: {r.status_code}")
        print(f"Content-Type: {r.headers.get('Content-Type')}")
        print("Response preview:")
        print(r.text[:500])
        return None


def iter_biotools(max_pages: int | None = None, sleep: float = 0.0):
    url = API_BASE
    page = 0

    headers = {
        "User-Agent": "research-software-attribute-study",
        "Accept": "application/json",
    }

    with requests.Session() as s:
        while url:
            page += 1
            if max_pages and page > max_pages:
                break

            for attempt in range(1, 6):
                try:
                    r = s.get(url, timeout=60, headers=headers)

                    if r.status_code == 429:
                        wait = max(5, sleep) * attempt
                        print(f"\nRate limited on page {page}. Waiting {wait}s...")
                        time.sleep(wait)
                        continue

                    if r.status_code >= 500:
                        wait = max(5, sleep) * attempt
                        print(f"\nServer error {r.status_code} on page {page}. Waiting {wait}s...")
                        time.sleep(wait)
                        continue

                    r.raise_for_status()
                    payload = safe_json_response(r)

                    if payload is None:
                        wait = max(5, sleep) * attempt
                        print(f"Retrying page {page} in {wait}s...")
                        time.sleep(wait)
                        continue

                    break

                except requests.RequestException as e:
                    wait = max(5, sleep) * attempt
                    print(f"\nRequest failed on page {page}: {e}")
                    print(f"Retrying in {wait}s...")
                    time.sleep(wait)

            else:
                print(f"\nFailed to fetch page {page} after 5 attempts. Stopping.")
                break

            for item in payload.get("list", []):
                yield item

            nxt = payload.get("next")
            url = urljoin("https://bio.tools/api/t/", nxt) if nxt else None

            if sleep:
                time.sleep(sleep)


def flatten_tool(tool: dict[str, Any], fetch_readmes: bool = False, sleep: float = 0.0) -> dict[str, Any]:
    topics = tool.get("topic") or []
    topic_terms = [t.get("term", "") for t in topics if isinstance(t, dict) and t.get("term")]
    topic_uris = [t.get("uri", "") for t in topics if isinstance(t, dict) and t.get("uri")]
    publications = tool.get("publication") or []
    pub_dois, pub_pmids, pub_pmcids, pub_notes = [], [], [], []
    for p in publications:
        if not isinstance(p, dict):
            continue
        if p.get("doi"): pub_dois.append(str(p["doi"]))
        if p.get("pmid"): pub_pmids.append(str(p["pmid"]))
        if p.get("pmcid"): pub_pmcids.append(str(p["pmcid"]))
        if p.get("note"): pub_notes.append(str(p["note"]))
        if p.get("metadata"): pub_notes.append(normalise_text(p["metadata"]))
    repo = github_url_from_tool(tool)
    readme = ""
    if fetch_readmes and repo:
        readme = fetch_readme(repo)
        if sleep:
            time.sleep(sleep)
    link_terms = []
    for field in ["link", "download", "documentation"]:
        for item in tool.get(field) or []:
            if isinstance(item, dict):
                link_terms.append(normalise_text([item.get("type"), item.get("note"), item.get("url")]))
    function_terms = []
    for f in tool.get("function") or []:
        if not isinstance(f, dict):
            continue
        function_terms.append(normalise_text(f.get("note")))
        for key in ["operation", "input", "output"]:
            function_terms.append(normalise_text(f.get(key)))
    return {
        "biotools_id": tool.get("biotoolsID", ""),
        "name": tool.get("name", ""),
        "description": normalise_text(tool.get("description", "")),
        "homepage": tool.get("homepage", ""),
        "github_url": repo,
        "readme": readme,
        "repo_title": repo.rstrip("/").split("/")[-1] if repo else tool.get("name", ""),
        "keywords": normalise_text([tool.get("toolType", []), tool.get("language", []), tool.get("operatingSystem", []), tool.get("license", "")]),
        "topic_terms": "|".join(topic_terms),
        "topic_uris": "|".join(topic_uris),
        "n_topics": len(set(topic_terms)),
        "primary_topic": topic_terms[0] if topic_terms else "",
        "doi": "|".join(pub_dois),
        "pmid": "|".join(pub_pmids),
        "pmcid": "|".join(pub_pmcids),
        "publication_note": normalise_text(pub_notes),
        "paper_title": "",      # to be enriched from publication DOI/PMID
        "abstract": "",         # to be enriched from publication DOI/PMID
        "function_text": normalise_text(function_terms),
        "link_text": normalise_text(link_terms),
        "addition_date": tool.get("additionDate", ""),
        "last_update": tool.get("lastUpdate", ""),
        "has_github": bool(repo),
        "has_publication": bool(pub_dois or pub_pmids or pub_pmcids),
        "has_topic": bool(topic_terms),
    }


def write_outputs(df: pd.DataFrame, out_dir: Path, min_class_count: int) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_dir / "biotools_flat_all.csv", index=False)

    # Fully matching subset: topic + GitHub + publication, because it can mirror paper/repo setup.
    full = df[df.has_topic & df.has_github & df.has_publication].copy()
    full.to_csv(out_dir / "biotools_multilabel.csv", index=False)

    single = full[full["n_topics"] == 1].copy()
    counts = single["primary_topic"].value_counts()
    keep = set(counts[counts >= min_class_count].index)
    single = single[single["primary_topic"].isin(keep)].copy()
    single.to_csv(out_dir / "biotools_singlelabel.csv", index=False)

    rows = []
    for name, sub in [("all", df), ("fully_matching_multilabel", full), ("singlelabel_min_count", single)]:
        rows.append({
            "dataset": name,
            "n_rows": len(sub),
            "n_with_github": int(sub.has_github.sum()) if len(sub) else 0,
            "n_with_publication": int(sub.has_publication.sum()) if len(sub) else 0,
            "n_with_topic": int(sub.has_topic.sum()) if len(sub) else 0,
            "n_classes": sub["primary_topic"].nunique() if "primary_topic" in sub else 0,
        })
    pd.DataFrame(rows).to_csv(out_dir / "biotools_dataset_summary.csv", index=False)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", type=Path, default=Path("data/biotools"))
    ap.add_argument("--max-pages", type=int, default=None, help="Debug only; omit for full 33k+ API dump.")
    ap.add_argument("--fetch-readmes", action="store_true", help="Fetch README.md from detected GitHub repos.")
    ap.add_argument("--sleep", type=float, default=0.0, help="Delay between API/GitHub requests.")
    ap.add_argument("--min-class-count", type=int, default=20)
    args = ap.parse_args()

    args.out_dir.mkdir(parents=True, exist_ok=True)
    raw_path = args.out_dir / "biotools_raw.jsonl"
    records = []
    with raw_path.open("w", encoding="utf-8") as f:
        for tool in tqdm(iter_biotools(args.max_pages, args.sleep), desc="bio.tools entries"):
            f.write(json.dumps(tool, ensure_ascii=False) + "\n")
            records.append(flatten_tool(tool, fetch_readmes=args.fetch_readmes, sleep=args.sleep))
    df = pd.DataFrame(records)
    write_outputs(df, args.out_dir, args.min_class_count)
    print(f"Wrote {len(df):,} records to {args.out_dir}")

if __name__ == "__main__":
    main()
