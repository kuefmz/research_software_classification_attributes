# Research Software Classification Attributes

This repository prepares reproducible datasets for comparing which metadata
attributes help classify research software. The current implementation focuses
on the data preparation pipeline for Papers with Code and bio.tools.

## Reproduce the Local Analysis

The paper analysis can be rerun from saved local files only. This command does
not download data, query GitHub or OpenAlex, call external APIs, or rerun SoMEF:

```bash
poetry run python scripts/run_full_analysis.py
```

Equivalent Make target:

```bash
make analysis
```

For a fast documentation/table/figure refresh that reuses already saved
classification metrics:

```bash
make analysis-fast
```

## Reproducible Training

The final training/evaluation entry point is:

```bash
poetry run python scripts/run_final_results.py --models local_all --folds 3 --include-heavy-skipped
```

This runs local training that does not update transformer weights: TF-IDF
baselines, including random forest, plus frozen BERT-family embedding pipelines
with lightweight downstream classifiers.

To also run local instruction-tuned prompting, first select an exact local model
identifier and a local runtime command that reads prompts from stdin and returns
structured JSON:

```bash
poetry run python scripts/run_final_results.py --models all --folds 3 --include-heavy-skipped --enable-local-llm --local-llm-model XXX_LOCAL_LLM_MODEL --local-llm-command "YOUR_LOCAL_RUNTIME_COMMAND" --append-results
```

The local LLM prompt template is versioned in
`prompts/local_llm_research_software_classifier.md`, copied into each run under
`final_results/prompt_templates/`, and response caches are saved under
`final_results/local_llm_cache/`. Full prompt/response attempts are saved under
`final_results/local_llm_conversations/`. No data is sent to an external
commercial API by this runner.

To resume local-only training and skip completed rows that are
already saved in `final_results/tables/classification_results.csv`:

```bash
make training-local-all-resume
```

The full protocol, model list, output manifest, and smoke-test commands are in
`docs/reproducible_training.md`.

Quick 10-record smoke check without touching `final_results/`:

```bash
poetry run python scripts/run_final_results.py --skip-dataset-build --datasets pwc_single_only --attributes abstract_only --models tfidf_logistic_regression,tfidf_random_forest --smoke-test-records 10
```

Quick 10-record smoke check for every configured pipeline, including frozen
BERT/RoBERTa-family embeddings and local LLM rows documented as not run unless a
runtime is supplied:

```bash
make training-smoke-all
```

The local-only runner validates required inputs, copies standardized processed
datasets to `data/processed/`, writes tables to `results/tables/`, writes PNG
and PDF figures to `results/figures/`, stores logs/configuration in
`results/logs/` and `results/reports/`, and creates
`results/reports/analysis_summary.md`.

Required saved local inputs include:

- Papers with Code merged data: `data/pwc_merged/pwc_merged_relevant_attributes.jsonl`
- bio.tools data: `data/biotools/biotools_flat_all.csv` and `data/biotools/biotools_raw.jsonl`
- aligned/intermediate data: `data/intermediate/pwc/` and `data/intermediate/biotools/`
- saved README/GitHub/SOMEF artifacts: `data/intermediate/github_enrichment/repository_artifacts/`
- final saved datasets: `data/final/*with_somef.jsonl` and `data/final/combined_all.jsonl`

The following steps are intentionally skipped by `scripts/run_full_analysis.py`
because they require external or expensive work:

- rerunning SoMEF
- downloading Papers with Code or bio.tools data
- querying GitHub or fetching README files
- querying OpenAlex or other metadata services
- calling external embedding or LLM APIs

## Outputs

The reproducible analysis writes:

- `data/processed/*.jsonl` and `data/processed/*.csv`: cleaned local dataset copies
- `results/tables/dataset_overview.csv`: source/dataset sizes and key metadata counts
- `results/tables/attribute_coverage.csv`: before/after SOMEF and source-level coverage
- `results/tables/label_distribution.csv`: class/category support by source
- `results/tables/missing_values.csv`: missing-value statistics
- `results/tables/classification_results.csv`: local TF-IDF model metrics when available
- `results/tables/best_attribute_model_combinations.csv`: best model/attribute combinations
- `results/figures/*.png` and `results/figures/*.pdf`: dataset, coverage, label, missingness, and classification plots
- `results/reports/analysis_summary.md`: short result summary for the paper
- `results/reports/analysis_run_config.json`: deterministic run configuration and input/output manifest
- `results/logs/full_analysis.log`: analysis run log

## Setup

Install the project dependencies with Poetry:

```bash
poetry install
poetry run pip install -r requirements.txt
```

For GitHub enrichment, set a token to increase API limits:

```bash
export GITHUB_TOKEN=...
```

For OpenAlex DOI metadata enrichment, an API key and mailto address are optional
but recommended for traceable, polite API use:

```bash
export OPENALEX_API_KEY=...
export OPENALEX_MAILTO=you@example.org
```

SoMEF enrichment is optional. Install SoMEF in the same environment if you want
README-derived metadata extraction.

## Folder Structure

The pipeline keeps raw, intermediate, and final data separate:

```text
data/
  raw/
    pwc/
    biotools/
  intermediate/
    pwc/
    biotools/
    github_enrichment/
  final/
  splits/
results/
  summary/
  per_class/
  predictions/
scripts/
src/
notebooks/
```

Existing local inputs are also supported:

- `data/pwc_merged/pwc_merged_relevant_attributes.jsonl`
- `data/biotools/biotools_flat_all.csv`
- `data/biotools/biotools_raw.jsonl`

## Data Preparation Pipeline

Run the base reproducible data preparation pipeline from the repository root:

```bash
poetry run python scripts/00_run_data_preparation.py
```

This single orchestrator runs:

```bash
poetry run python scripts/01_align_pwc.py
poetry run python scripts/02_align_biotools.py
poetry run python scripts/03_enrich_biotools_publications.py
poetry run python scripts/04_create_ml_datasets.py
```

The base pipeline intentionally does not fetch GitHub README content and does
not run SoMEF. It prepares the cleaned PwC and bio.tools datasets needed before
README-based enrichment.

The shared aligned schema is:

```json
{
  "source": "...",
  "item_id": "...",
  "software_name": "...",
  "software_description": "...",
  "paper_title": "...",
  "paper_abstract": "...",
  "publication_url": "...",
  "repository_url": "...",
  "repository_urls": [],
  "labels": [],
  "secondary_labels": [],
  "tasks": [],
  "methods": []
}
```

The GitHub enrichment script caches one JSONL row per repository in
`data/intermediate/github_enrichment/github_repository_cache.jsonl`, so repeated
runs do not fetch the same repository twice. Failures are stored with an `error`
field and do not stop the run.

The bio.tools publication enrichment script uses DOI values to query OpenAlex
and caches one JSONL row per DOI in
`data/intermediate/biotools/openalex_publication_cache.jsonl`. When a bio.tools
entry contains multiple DOI values, alignment creates one row per DOI so each
publication can be treated as a separate training item. OpenAlex title and
abstract metadata are stored in
`data/intermediate/biotools/biotools_publication_enriched.jsonl`.

The final dataset cleanup rules are:

- Papers with Code records must have a GitHub repository URL.
- The Papers with Code label `General` is removed before single-label and
  multi-label dataset construction.
- bio.tools records must have a GitHub repository URL.
- bio.tools records must have a DOI-backed publication URL.
- Every filtering step is logged and summarized in
  `data/final/dataset_filtering_summary.csv`.

The final dataset script writes:

- `data/final/pwc_single_label.jsonl`
- `data/final/pwc_multi_label.jsonl`
- `data/final/biotools_single_label.jsonl`
- `data/final/biotools_multi_label.jsonl`
- `data/final/combined_all.jsonl`
- `data/final/dataset_filtering_summary.csv`

Single-label datasets keep records with exactly one label and expose `label` as
a string. Multi-label datasets keep records with at least one label and expose
`label` as a list.

## Attribute Combinations

Reusable text combinations are defined in `src/config.py` and built with
`src.utils.text_utils.build_attribute_texts`. They include `abstract_only`,
`readme_only`, `abstract_readme`, `all_repository_metadata`, and
`all_non_target_textual_metadata`. Target-derived fields such as `labels`,
`tasks`, `methods`, and `secondary_labels` are excluded from predictor text.

## Reproducibility Notes

- Paths, random seed, model defaults, label columns, text attributes, and GitHub
  rate-limit settings live in `src/config.py`.
- Scripts log record counts and before/after filtering counts.
- Large outputs are written as JSONL.
- Writes use temporary files and atomic replacement where practical.
- Raw data is never deleted or overwritten by the preparation scripts.

## Preparing README and SoMEF Enrichment

The next step after the base datasets is GitHub README enrichment:

```bash
poetry run python scripts/03_enrich_github_metadata.py
```

This prepares `readme_content`, repository titles, descriptions, topics,
licenses, and normalized GitHub URLs. Do not enable SoMEF until this file exists
and README coverage has been inspected.

To run SoMEF later, set `RUN_SOMEF_ENRICHMENT = True` in `src/config.py` and
rerun:

```bash
poetry run python scripts/04_create_ml_datasets.py
```

SoMEF results are cached in
`data/intermediate/github_enrichment/somef_cache.jsonl`.

## Public Metadata Source

OpenAlex is used for DOI-based publication metadata because it provides an open
REST API and complete data snapshot. The API supports `/works` queries and DOI
lookup, including batch DOI filters. See the OpenAlex developer documentation:
https://developers.openalex.org/

Publication titles and abstracts are cleaned before final dataset creation:
HTML/XML tags are removed, HTML entities are decoded, Markdown links are
collapsed to their visible text, and whitespace is normalized.

Papers with Code records also include a `doi` field when a DOI can be extracted
from available metadata. Many PwC records point to arXiv rather than DOI-backed
publication pages, so `doi` may be empty for those rows.

## SoMEF Enrichment Script

README and SoMEF enrichment is prepared but not part of the base orchestrator,
because it can run for a long time. The script is:

```bash
poetry run python scripts/05_enrich_somef_metadata.py
```

Before running it, configure SoMEF:

```bash
poetry run pip install somef
poetry run python -m nltk.downloader wordnet
poetry run python -m nltk.downloader omw-1.4
poetry run somef configure
```

When `somef configure` asks for a GitHub authentication token, you can provide a
GitHub personal access token. This script runs SoMEF on saved README files, so it
does not need SoMEF to fetch repositories itself, but configuring SoMEF is still
recommended for reproducibility and for any future `somef describe -r` use.

```bash
export GITHUB_TOKEN=...
```

The script fetches README files without the GitHub API by trying raw GitHub URLs
such as:

```bash
https://raw.githubusercontent.com/owner/repo/HEAD/README.md
```

It then follows the documented SoMEF CLI pattern for local README files:

```bash
somef describe -d README.md -o somef.json -t 0.8
```

To avoid repeated work, each repository gets its own artifact folder:

```text
data/intermediate/github_enrichment/repository_artifacts/<owner__repo>/
```

Inside that folder, the script saves:

```text
README.md
somef.json
metadata.json
```

Existing `README.md` and `somef.json` files are reused. Missing README files are
fetched one at a time with `README_FETCH_SLEEP_SECONDS` between requests. Missing
SoMEF outputs are generated one at a time with `SOMEF_SLEEP_SECONDS` between
runs. Both values are defined in `src/config.py`. The raw SoMEF JSON files are
kept so you can extract additional fields later without rerunning SoMEF.

Every attempted repository is also logged to:

```text
data/intermediate/github_enrichment/somef_run_manifest.jsonl
```

The manifest records whether each repository README or SoMEF JSON was skipped
because it already existed, saved successfully, or failed. This is useful for
resuming after interrupted runs.

The script writes new dataset versions:

- `data/final/pwc_single_label_with_somef.jsonl`
- `data/final/pwc_multi_label_with_somef.jsonl`
- `data/final/biotools_single_label_with_somef.jsonl`
- `data/final/biotools_multi_label_with_somef.jsonl`
- `data/final/combined_all_with_somef.jsonl`

These files add `readme_content`, `readme_path`, `repository_artifact_dir`,
`repository_title`, `somef_description`, `somef_citation`, `somef_title`,
`somef_keywords`, `somef_json_path`, and `somef_error`.

Official SoMEF documentation used for these commands:
https://somef.readthedocs.io/en/latest/

## Next Steps

The next implementation stage should add deterministic split creation and the
classical, embedding, transformer, LLM, and result collection scripts listed in
the paper plan.
