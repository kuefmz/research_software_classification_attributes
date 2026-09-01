#!/usr/bin/env python3

from pathlib import Path
import json

import pandas as pd


INPUT_FILE = "data/biotools/biotools_flat_all.csv"
OUTPUT_JSON = "data/biotools/biotools_pwc_aligned.json"
OUTPUT_CSV = "data/biotools/biotools_pwc_aligned.csv"


def clean(value):
    if pd.isna(value):
        return ""
    return str(value).strip()


def split_pipe(value):
    value = clean(value)
    if not value:
        return []
    return [v.strip() for v in value.split("|") if v.strip()]


def publication_url(row):
    dois = split_pipe(row.get("doi", ""))
    pmids = split_pipe(row.get("pmid", ""))
    pmcids = split_pipe(row.get("pmcid", ""))

    if dois:
        doi = dois[0].replace("https://doi.org/", "")
        return f"https://doi.org/{doi}"

    if pmids:
        return f"https://pubmed.ncbi.nlm.nih.gov/{pmids[0]}/"

    if pmcids:
        return f"https://www.ncbi.nlm.nih.gov/pmc/articles/{pmcids[0]}/"

    return ""


def build_record(row):
    repository_url = clean(row.get("github_url", ""))

    labels = split_pipe(row.get("topic_terms", ""))

    operation_terms = split_pipe(row.get("operation_terms", ""))
    if not operation_terms:
        operation_terms = split_pipe(row.get("edam_operation_terms", ""))

    return {
        "source": "bio.tools",
        "item_id": clean(row.get("biotools_id", "")),
        "software_name": clean(row.get("name", "")),
        "software_description": clean(row.get("description", "")),
        "paper_title": clean(row.get("paper_title", "")),
        "paper_abstract": clean(row.get("abstract", "")),
        "publication_url": publication_url(row),
        "repository_url": repository_url,
        "repository_urls": [repository_url] if repository_url else [],
        "labels": labels,
        "secondary_labels": operation_terms,
        "tasks": operation_terms,
        "methods": [],
    }


def main():
    df = pd.read_csv(INPUT_FILE).fillna("")

    records = []

    for _, row in df.iterrows():
        records.append(build_record(row))

    Path(OUTPUT_JSON).parent.mkdir(parents=True, exist_ok=True)

    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)

    rows = []

    for record in records:
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

    pd.DataFrame(rows).to_csv(OUTPUT_CSV, index=False)

    print(f"Wrote {len(records):,} records")
    print(f"JSON: {OUTPUT_JSON}")
    print(f"CSV:  {OUTPUT_CSV}")


if __name__ == "__main__":
    main()