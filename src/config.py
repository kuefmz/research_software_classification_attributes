"""Central configuration for the reproducible data preparation pipeline.

The project deliberately keeps paths and experiment constants in one importable
module instead of scattering command-line defaults across scripts. Scripts are
therefore runnable as ``python scripts/<name>.py`` and use the same folders,
random seed, label fields, and metadata attribute definitions.
"""
from __future__ import annotations

from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent

DATA_DIR = BASE_DIR / "data"
RAW_DATA_DIR = DATA_DIR / "raw"
INTERMEDIATE_DATA_DIR = DATA_DIR / "intermediate"
FINAL_DATA_DIR = DATA_DIR / "final"
SPLITS_DIR = DATA_DIR / "splits"

RAW_PWC_DIR = RAW_DATA_DIR / "pwc"
RAW_BIOTOOLS_DIR = RAW_DATA_DIR / "biotools"

LEGACY_PWC_MERGED_DIR = DATA_DIR / "pwc_merged"
LEGACY_BIOTOOLS_DIR = DATA_DIR / "biotools"
LEGACY_PWC_RAW_DIR = DATA_DIR / "orig_pow_archive"

INTERMEDIATE_PWC_DIR = INTERMEDIATE_DATA_DIR / "pwc"
INTERMEDIATE_BIOTOOLS_DIR = INTERMEDIATE_DATA_DIR / "biotools"
GITHUB_ENRICHMENT_DIR = INTERMEDIATE_DATA_DIR / "github_enrichment"

RESULTS_DIR = BASE_DIR / "results"
RESULTS_SUMMARY_DIR = RESULTS_DIR / "summary"
RESULTS_PER_CLASS_DIR = RESULTS_DIR / "per_class"
RESULTS_PREDICTIONS_DIR = RESULTS_DIR / "predictions"

PWC_MERGED_JSONL = LEGACY_PWC_MERGED_DIR / "pwc_merged_relevant_attributes.jsonl"
BIOTOOLS_FLAT_CSV = LEGACY_BIOTOOLS_DIR / "biotools_flat_all.csv"
BIOTOOLS_RAW_JSONL = LEGACY_BIOTOOLS_DIR / "biotools_raw.jsonl"

PWC_ALIGNED_JSONL = INTERMEDIATE_PWC_DIR / "pwc_aligned.jsonl"
PWC_ALIGNED_CSV = INTERMEDIATE_PWC_DIR / "pwc_aligned.csv"
BIOTOOLS_ALIGNED_JSONL = INTERMEDIATE_BIOTOOLS_DIR / "biotools_aligned.jsonl"
BIOTOOLS_ALIGNED_CSV = INTERMEDIATE_BIOTOOLS_DIR / "biotools_aligned.csv"
BIOTOOLS_PUBLICATION_CACHE_JSONL = INTERMEDIATE_BIOTOOLS_DIR / "openalex_publication_cache.jsonl"
BIOTOOLS_PUBLICATION_ENRICHED_JSONL = INTERMEDIATE_BIOTOOLS_DIR / "biotools_publication_enriched.jsonl"
BIOTOOLS_PUBLICATION_ENRICHED_CSV = INTERMEDIATE_BIOTOOLS_DIR / "biotools_publication_enriched.csv"

GITHUB_CACHE_JSONL = GITHUB_ENRICHMENT_DIR / "github_repository_cache.jsonl"
GITHUB_ENRICHED_JSONL = GITHUB_ENRICHMENT_DIR / "aligned_with_github_metadata.jsonl"
SOMEF_CACHE_JSONL = GITHUB_ENRICHMENT_DIR / "somef_cache.jsonl"
SOMEF_JSON_DIR = GITHUB_ENRICHMENT_DIR / "somef_jsons"
REPOSITORY_ARTIFACTS_DIR = GITHUB_ENRICHMENT_DIR / "repository_artifacts"
SOMEF_RUN_MANIFEST_JSONL = GITHUB_ENRICHMENT_DIR / "somef_run_manifest.jsonl"
SOMEF_RUN_LOG = GITHUB_ENRICHMENT_DIR / "somef_run.log"
SOMEF_DATASET_JSONL = FINAL_DATA_DIR / "combined_all_with_somef.jsonl"
SOMEF_SLEEP_SECONDS = 0.5
SOMEF_THRESHOLD = 0.2
README_FETCH_SLEEP_SECONDS = 0.2

PWC_SINGLE_LABEL_JSONL = FINAL_DATA_DIR / "pwc_single_label.jsonl"
PWC_MULTI_LABEL_JSONL = FINAL_DATA_DIR / "pwc_multi_label.jsonl"
BIOTOOLS_SINGLE_LABEL_JSONL = FINAL_DATA_DIR / "biotools_single_label.jsonl"
BIOTOOLS_MULTI_LABEL_JSONL = FINAL_DATA_DIR / "biotools_multi_label.jsonl"
COMBINED_ALL_JSONL = FINAL_DATA_DIR / "combined_all.jsonl"
DATASET_FILTERING_SUMMARY_CSV = FINAL_DATA_DIR / "dataset_filtering_summary.csv"
PWC_SINGLE_LABEL_WITH_SOMEF_JSONL = FINAL_DATA_DIR / "pwc_single_label_with_somef.jsonl"
PWC_MULTI_LABEL_WITH_SOMEF_JSONL = FINAL_DATA_DIR / "pwc_multi_label_with_somef.jsonl"
BIOTOOLS_SINGLE_LABEL_WITH_SOMEF_JSONL = FINAL_DATA_DIR / "biotools_single_label_with_somef.jsonl"
BIOTOOLS_MULTI_LABEL_WITH_SOMEF_JSONL = FINAL_DATA_DIR / "biotools_multi_label_with_somef.jsonl"

RANDOM_SEED = 42

SCHEMA_FIELDS = [
    "source",
    "item_id",
    "software_name",
    "software_description",
    "paper_title",
    "paper_abstract",
    "publication_url",
    "repository_url",
    "repository_urls",
    "labels",
    "secondary_labels",
    "tasks",
    "methods",
]

BIOTOOLS_EXTRA_FIELDS = [
    "doi",
    "metadata_source",
    "metadata_error",
    "publication_year",
    "publication_type",
    "openalex_id",
]

LABEL_COLUMNS = ["labels", "secondary_labels", "tasks", "methods"]
TARGET_FIELDS = ["labels"]
EXCLUDED_LEAKAGE_FIELDS = ["labels", "secondary_labels", "tasks", "methods"]

NON_TARGET_TEXT_ATTRIBUTES = [
    "paper_title",
    "paper_abstract",
    "software_name",
    "software_description",
    "repository_title",
    "repository_description",
    "repository_keywords",
    "readme_content",
    "somef_description",
]

ATTRIBUTE_COMBINATIONS = {
    "abstract_only": ["paper_abstract"],
    "title_only": ["paper_title"],
    "publication_text": ["paper_title", "paper_abstract"],
    "repository_description": ["repository_description", "software_description"],
    "readme_only": ["readme_content"],
    "repository_text": ["repository_title", "repository_description", "readme_content"],
    "somef_description_only": ["somef_description"],
    "repository_title_keywords": ["repository_title", "repository_keywords"],
    "abstract_readme": ["paper_abstract", "readme_content"],
    "abstract_description": ["paper_abstract", "software_description", "repository_description"],
    "abstract_repository_title_keywords": ["paper_abstract", "repository_title", "repository_keywords"],
    "abstract_readme_description": [
        "paper_abstract",
        "readme_content",
        "software_description",
        "repository_description",
    ],
    "all_publication_metadata": ["paper_title", "paper_abstract", "publication_url"],
    "all_repository_metadata": [
        "repository_title",
        "repository_description",
        "repository_keywords",
        "readme_content",
        "somef_description",
    ],
    "all_non_target_textual_metadata": NON_TARGET_TEXT_ATTRIBUTES,
}

MODEL_PARAMS = {
    "tfidf": {"max_features": 50000, "ngram_range": (1, 2), "min_df": 2},
    "logistic_regression": {"max_iter": 3000, "class_weight": "balanced"},
    "linear_svm": {"class_weight": "balanced"},
    "random_forest": {"n_estimators": 300, "random_state": RANDOM_SEED, "n_jobs": -1},
}

GITHUB_API_BASE = "https://api.github.com"
GITHUB_REQUEST_TIMEOUT = 30
GITHUB_RATE_LIMIT_SLEEP_SECONDS = 0.5
GITHUB_METADATA_SLEEP_SECONDS = 0.5
GITHUB_USER_AGENT = "research-software-classification-attributes"
GITHUB_TOKEN_ENV_VAR = "GITHUB_TOKEN"

OPENALEX_API_BASE = "https://api.openalex.org"
OPENALEX_API_KEY_ENV_VAR = "OPENALEX_API_KEY"
OPENALEX_MAILTO_ENV_VAR = "OPENALEX_MAILTO"
OPENALEX_REQUEST_TIMEOUT = 30
OPENALEX_BATCH_SIZE = 50

# Keep disabled for the base PwC/bio.tools final datasets. Set to True after
# GitHub README enrichment when SoMEF-derived metadata is explicitly needed.
RUN_SOMEF_ENRICHMENT = False

EXCLUDED_LABELS_BY_SOURCE = {
    "papers_with_code": {"General"},
}


def ensure_directories() -> None:
    """Create the directory layout used by the data preparation scripts."""
    for path in [
        RAW_PWC_DIR,
        RAW_BIOTOOLS_DIR,
        INTERMEDIATE_PWC_DIR,
        INTERMEDIATE_BIOTOOLS_DIR,
        GITHUB_ENRICHMENT_DIR,
        SOMEF_JSON_DIR,
        REPOSITORY_ARTIFACTS_DIR,
        FINAL_DATA_DIR,
        SPLITS_DIR,
        RESULTS_SUMMARY_DIR,
        RESULTS_PER_CLASS_DIR,
        RESULTS_PREDICTIONS_DIR,
    ]:
        path.mkdir(parents=True, exist_ok=True)
