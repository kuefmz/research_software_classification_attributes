#!/usr/bin/env python3
"""Run the final reproducible analysis from the root-level final datasets."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import logging
import os
import platform
import shlex
import subprocess
import sys
import time
import warnings
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from sklearn.base import BaseEstimator, ClassifierMixin, clone
from sklearn.ensemble import RandomForestClassifier
from sklearn.exceptions import ConvergenceWarning
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import SGDClassifier
from sklearn.metrics import (
    accuracy_score,
    balanced_accuracy_score,
    f1_score,
    hamming_loss,
    precision_recall_fscore_support,
    precision_score,
    recall_score,
)
from sklearn.model_selection import KFold, StratifiedKFold, train_test_split
from sklearn.multiclass import OneVsRestClassifier
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import LabelEncoder, MultiLabelBinarizer
from sklearn.svm import LinearSVC

sys.path.append(str(Path(__file__).resolve().parent.parent))

from src.utils.io_utils import read_jsonl
from src.utils.text_utils import build_text, clean_list


ROOT = Path(__file__).resolve().parent.parent
FINAL_DATASETS_DIR = ROOT / "final_datasets"
FINAL_RESULTS_DIR = ROOT / "final_results"
TABLES_DIR = FINAL_RESULTS_DIR / "tables"
FIGURES_DIR = FINAL_RESULTS_DIR / "figures"
REPORTS_DIR = FINAL_RESULTS_DIR / "reports"
PREDICTIONS_DIR = FINAL_RESULTS_DIR / "predictions"
SPLITS_DIR = FINAL_RESULTS_DIR / "splits"
LOGS_DIR = FINAL_RESULTS_DIR / "logs"
EMBEDDINGS_DIR = FINAL_RESULTS_DIR / "embeddings"
LOCAL_LLM_CACHE_DIR = FINAL_RESULTS_DIR / "local_llm_cache"
LOCAL_LLM_CONVERSATIONS_DIR = FINAL_RESULTS_DIR / "local_llm_conversations"
PROMPTS_DIR = FINAL_RESULTS_DIR / "prompt_templates"
LOG_PATH = LOGS_DIR / "final_analysis.log"
LOCAL_LLM_PROMPT_TEMPLATE = ROOT / "prompts" / "local_llm_research_software_classifier.md"

RANDOM_SEED = 42
TEST_SIZE = 0.2
MIN_RECORDS = 40
NO_PREDICTION_LABEL = "__NO_PREDICTION__"
TARGET_FIELDS = ["labels"]
EXCLUDED_LEAKAGE_FIELDS = ["labels", "tasks", "methods", "secondary_labels"]

ATTRIBUTE_COMBINATIONS = {
    "abstract_only": ["paper_abstract"],
    "title_only": ["paper_title"],
    "publication_text": ["paper_title", "paper_abstract"],
    "repository_description": ["repository_description", "software_description"],
    "readme_only": ["readme_content"],
    "repository_text": ["repository_title", "repository_description", "readme_content"],
    "somef_description_only": ["somef_description"],
    "repository_title_keywords": ["repository_title", "repository_keywords"],
    "abstract_readme_description": [
        "paper_abstract",
        "readme_content",
        "software_description",
        "repository_description",
    ],
    "abstract_repository_title_keywords": ["paper_abstract", "repository_title", "repository_keywords"],
    "all_publication_metadata": ["paper_title", "paper_abstract", "publication_url"],
    "all_repository_metadata": [
        "repository_title",
        "repository_description",
        "repository_keywords",
        "readme_content",
        "somef_description",
    ],
    "all_non_target_textual_metadata": [
        "paper_title",
        "paper_abstract",
        "software_name",
        "software_description",
        "repository_title",
        "repository_description",
        "repository_keywords",
        "readme_content",
        "somef_description",
    ],
}

SIMPLE_MODELS = [
    "tfidf_logistic_regression",
    "tfidf_linear_svm",
    "tfidf_random_forest",
    "tfidf_xgboost",
    "tfidf_hard_voting",
]

FROZEN_BERT_PIPELINES = {
    "modernbert_embedding_logistic_regression": {
        "hf_model_id": "answerdotai/ModernBERT-base",
        "classifier": "logistic_regression",
        "family": "frozen_transformer_embeddings",
        "description": "ModernBERT frozen mean-pooled embeddings followed by a deterministic linear classifier.",
    },
    "modernbert_embedding_random_forest": {
        "hf_model_id": "answerdotai/ModernBERT-base",
        "classifier": "random_forest",
        "family": "frozen_transformer_embeddings",
        "description": "ModernBERT frozen mean-pooled embeddings followed by random forest.",
    },
    "scibert_embedding_logistic_regression": {
        "hf_model_id": "allenai/scibert_scivocab_uncased",
        "classifier": "logistic_regression",
        "family": "frozen_transformer_embeddings",
        "description": "SciBERT scientific-domain frozen mean-pooled embeddings followed by a deterministic linear classifier.",
    },
    "scibert_embedding_random_forest": {
        "hf_model_id": "allenai/scibert_scivocab_uncased",
        "classifier": "random_forest",
        "family": "frozen_transformer_embeddings",
        "description": "SciBERT scientific-domain frozen mean-pooled embeddings followed by random forest.",
    },
    "deberta_v3_embedding_logistic_regression": {
        "hf_model_id": "microsoft/deberta-v3-base",
        "classifier": "logistic_regression",
        "family": "frozen_transformer_embeddings",
        "description": "DeBERTa-v3 frozen mean-pooled embeddings followed by a deterministic linear classifier.",
    },
    "deberta_v3_embedding_random_forest": {
        "hf_model_id": "microsoft/deberta-v3-base",
        "classifier": "random_forest",
        "family": "frozen_transformer_embeddings",
        "description": "DeBERTa-v3 frozen mean-pooled embeddings followed by random forest.",
    },
    "roberta_embedding_logistic_regression": {
        "hf_model_id": "FacebookAI/roberta-base",
        "classifier": "logistic_regression",
        "family": "frozen_transformer_embeddings",
        "description": "RoBERTa frozen mean-pooled embeddings followed by a deterministic linear classifier.",
    },
    "roberta_embedding_random_forest": {
        "hf_model_id": "FacebookAI/roberta-base",
        "classifier": "random_forest",
        "family": "frozen_transformer_embeddings",
        "description": "RoBERTa frozen mean-pooled embeddings followed by random forest.",
    },
}

LOCAL_LLM_PIPELINES = {
    "local_llm_zero_shot": {
        "family": "local_llm_prompting",
        "description": "Local instruction-tuned language model zero-shot structured-output classifier; no supervised training.",
    },
    "local_llm_one_shot": {
        "family": "local_llm_prompting",
        "description": "Local instruction-tuned language model one-shot structured-output classifier using one deterministic example from the training split; no supervised training.",
    },
    "local_llm_few_shot": {
        "family": "local_llm_prompting",
        "description": "Local instruction-tuned language model few-shot structured-output classifier using deterministic examples from the training split; no supervised training.",
    },
}

HEAVY_PIPELINES = [
    ("sbert_embedding_logistic_regression", "Pending: requires a selected local SBERT model identifier such as XXX_SBERT_MODEL."),
    ("sbert_embedding_linear_svm", "Pending: requires a selected local SBERT model identifier such as XXX_SBERT_MODEL."),
    ("specter_embedding_logistic_regression", "Pending: requires a selected local SPECTER/SPECTER2 model identifier such as XXX_SPECTER_MODEL."),
    ("specter_embedding_linear_svm", "Pending: requires a selected local SPECTER/SPECTER2 model identifier such as XXX_SPECTER_MODEL."),
    ("local_llm_zero_shot", "Pending: requires a selected local instruction-tuned model, local runtime command, and validation run."),
    ("local_llm_one_shot", "Pending: requires a selected local instruction-tuned model, local runtime command, and validation run."),
    ("local_llm_few_shot", "Pending: requires a selected local instruction-tuned model, local runtime command, and validation run."),
]

LOGGER = logging.getLogger("run_final_results")


@dataclass(frozen=True)
class ExperimentSpec:
    name: str
    family: str
    runnable: bool
    skip_reason: str = ""


class XGBLabelEncodedClassifier(BaseEstimator, ClassifierMixin):
    """Wrap XGBoost so string labels work inside sklearn pipelines."""

    def __init__(self, random_state: int = RANDOM_SEED):
        self.random_state = random_state

    def fit(self, x: Any, y: list[str] | np.ndarray) -> "XGBLabelEncodedClassifier":
        from xgboost import XGBClassifier

        self.encoder_ = LabelEncoder()
        y_encoded = self.encoder_.fit_transform(y)
        if len(self.encoder_.classes_) == 1:
            self.constant_class_ = self.encoder_.classes_[0]
            self.classes_ = self.encoder_.classes_
            return self
        self.constant_class_ = None
        objective = "binary:logistic" if len(self.encoder_.classes_) == 2 else "multi:softmax"
        params: dict[str, Any] = {}
        if len(self.encoder_.classes_) > 2:
            params["num_class"] = len(self.encoder_.classes_)
        self.model_ = XGBClassifier(
            n_estimators=60,
            max_depth=4,
            learning_rate=0.08,
            subsample=0.9,
            colsample_bytree=0.9,
            max_bin=64,
            objective=objective,
            eval_metric="mlogloss",
            tree_method="hist",
            n_jobs=-1,
            random_state=self.random_state,
            **params,
        )
        self.model_.fit(x, y_encoded)
        self.classes_ = self.encoder_.classes_
        return self

    def predict(self, x: Any) -> np.ndarray:
        if getattr(self, "constant_class_", None) is not None:
            return np.repeat(self.constant_class_, x.shape[0])
        return self.encoder_.inverse_transform(self.model_.predict(x).astype(int))

    def predict_proba(self, x: Any) -> np.ndarray:
        if getattr(self, "constant_class_", None) is not None:
            proba = np.zeros((x.shape[0], len(self.classes_)))
            proba[:, 0] = 1.0
            return proba
        proba = self.model_.predict_proba(x)
        if proba.ndim == 1:
            proba = np.vstack([1 - proba, proba]).T
        return proba


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skip-dataset-build", action="store_true", help="Use existing final_datasets/ files without rebuilding them.")
    parser.add_argument("--skip-training", action="store_true", help="Refresh tables/figures/report from existing result CSV files.")
    parser.add_argument(
        "--models",
        default="simple",
        help=(
            "Comma-separated model names, or one of: simple/classical, bert, local_all, local_llm, all. "
            "BERT models are frozen embedding extractors; transformer weights are not updated."
        ),
    )
    parser.add_argument("--datasets", default="all", help="Comma-separated dataset names, or 'all'.")
    parser.add_argument("--attributes", default="all", help="Comma-separated attribute set names, or 'all'.")
    parser.add_argument("--folds", type=int, default=0, help="Optional cross-validation folds. Use 3 or 5 for fold mean/std tables.")
    parser.add_argument("--max-features", type=int, default=5000, help="Maximum TF-IDF features.")
    parser.add_argument("--rf-trees", type=int, default=100, help="Random forest tree count.")
    parser.add_argument("--include-heavy-skipped", action="store_true", help="Add skipped rows for SBERT, transformers, and LLM experiments.")
    parser.add_argument("--append-results", action="store_true", help="Append/replace this run's rows in existing result tables instead of replacing all results.")
    parser.add_argument("--skip-existing-results", action="store_true", help="Resume a run by skipping completed rows already present in classification_results.csv.")
    parser.add_argument("--output-dir", default=None, help="Directory for generated results. Defaults to final_results/, or final_results_smoke/ in smoke-test mode.")
    parser.add_argument("--smoke-test-records", type=int, default=0, help="Deterministically limit each training dataset to this many records for quick validation.")
    parser.add_argument("--embedding-batch-size", type=int, default=16, help="Batch size for frozen transformer embedding extraction.")
    parser.add_argument("--embedding-progress-every", type=int, default=50, help="Log frozen-transformer embedding progress every N batches. Use 0 to disable batch progress logs.")
    parser.add_argument("--embedding-max-length", type=int, default=512, help="Tokenizer max sequence length for frozen transformer embeddings.")
    parser.add_argument("--embedding-device", default="auto", help="Embedding device: auto, cpu, cuda, cuda:0, etc.")
    parser.add_argument("--offline-models-only", action="store_true", help="Load Hugging Face models from the local cache only.")
    parser.add_argument("--trust-remote-code", action="store_true", help="Allow Hugging Face models that require remote model code.")
    parser.add_argument("--enable-local-llm", action="store_true", help="Run local_llm_* models through a user-supplied local runtime command.")
    parser.add_argument("--local-llm-model", default=os.environ.get("LOCAL_LLM_MODEL", "XXX_LOCAL_LLM_MODEL"), help="Local instruction-tuned model identifier.")
    parser.add_argument("--local-llm-command", default=os.environ.get("LOCAL_LLM_COMMAND", ""), help="Command used to run the local LLM; the prompt is passed on stdin.")
    parser.add_argument("--local-llm-temperature", type=float, default=0.0, help="Local LLM sampling temperature; keep 0 for deterministic generation.")
    parser.add_argument("--local-llm-max-metadata-chars", type=int, default=6000, help="Maximum metadata characters included in each local LLM prompt.")
    parser.add_argument("--local-llm-few-shot-examples", type=int, default=4, help="Number of deterministic few-shot examples to include.")
    parser.add_argument("--local-llm-max-retries", type=int, default=2, help="Retry count for invalid or unparsable local LLM JSON responses.")
    parser.add_argument("--local-llm-timeout", type=int, default=180, help="Timeout in seconds for each local LLM command invocation.")
    parser.add_argument("--local-llm-sleep-seconds", type=float, default=0.0, help="Optional delay between local LLM calls.")
    parser.add_argument("--local-llm-on-cv", action="store_true", help="Run local LLM prompting on CV folds too. Disabled by default because prompting can be slow.")
    return parser.parse_args()


def configure_logging() -> None:
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[logging.StreamHandler(), logging.FileHandler(LOG_PATH, encoding="utf-8")],
    )


def ensure_dirs() -> None:
    for path in [
        TABLES_DIR,
        FIGURES_DIR,
        REPORTS_DIR,
        PREDICTIONS_DIR,
        SPLITS_DIR,
        LOGS_DIR,
        EMBEDDINGS_DIR,
        LOCAL_LLM_CACHE_DIR,
        LOCAL_LLM_CONVERSATIONS_DIR,
        PROMPTS_DIR,
    ]:
        path.mkdir(parents=True, exist_ok=True)


def configure_output_paths(output_dir: Path) -> None:
    """Route generated files to a normal or smoke-test results directory."""
    global FINAL_RESULTS_DIR, TABLES_DIR, FIGURES_DIR, REPORTS_DIR, PREDICTIONS_DIR
    global SPLITS_DIR, LOGS_DIR, EMBEDDINGS_DIR, LOCAL_LLM_CACHE_DIR, LOCAL_LLM_CONVERSATIONS_DIR, PROMPTS_DIR, LOG_PATH

    FINAL_RESULTS_DIR = output_dir
    TABLES_DIR = FINAL_RESULTS_DIR / "tables"
    FIGURES_DIR = FINAL_RESULTS_DIR / "figures"
    REPORTS_DIR = FINAL_RESULTS_DIR / "reports"
    PREDICTIONS_DIR = FINAL_RESULTS_DIR / "predictions"
    SPLITS_DIR = FINAL_RESULTS_DIR / "splits"
    LOGS_DIR = FINAL_RESULTS_DIR / "logs"
    EMBEDDINGS_DIR = FINAL_RESULTS_DIR / "embeddings"
    LOCAL_LLM_CACHE_DIR = FINAL_RESULTS_DIR / "local_llm_cache"
    LOCAL_LLM_CONVERSATIONS_DIR = FINAL_RESULTS_DIR / "local_llm_conversations"
    PROMPTS_DIR = FINAL_RESULTS_DIR / "prompt_templates"
    LOG_PATH = LOGS_DIR / "final_analysis.log"


def load_dotenv_if_available() -> None:
    """Load local environment defaults without requiring python-dotenv."""
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    load_dotenv(ROOT / ".env")


def stable_json_hash(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def package_versions() -> dict[str, str]:
    packages = ["numpy", "pandas", "sklearn", "scipy", "xgboost", "transformers", "torch", "dotenv", "sentencepiece"]
    versions = {"python": sys.version.split()[0], "platform": sys.platform}
    for package in packages:
        try:
            module = __import__(package)
            versions[package] = getattr(module, "__version__", "unknown")
        except ImportError:
            versions[package] = "not_installed"
    return versions


def model_slug(model_id: str) -> str:
    return "".join(char if char.isalnum() else "_" for char in model_id).strip("_")


def write_prompt_template_snapshot() -> str:
    """Copy the source-controlled local LLM prompt into final_results."""
    if not LOCAL_LLM_PROMPT_TEMPLATE.exists():
        raise FileNotFoundError(f"Missing local LLM prompt template: {LOCAL_LLM_PROMPT_TEMPLATE}")
    text = LOCAL_LLM_PROMPT_TEMPLATE.read_text(encoding="utf-8")
    (PROMPTS_DIR / LOCAL_LLM_PROMPT_TEMPLATE.name).write_text(text, encoding="utf-8")
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def build_final_datasets(skip: bool) -> None:
    if skip:
        LOGGER.info("Skipping final dataset package rebuild")
        return
    subprocess.run([sys.executable, str(ROOT / "scripts" / "build_final_datasets_package.py")], cwd=ROOT, check=True)


def load_jsonl(name: str) -> list[dict[str, Any]]:
    path = FINAL_DATASETS_DIR / name
    if not path.exists():
        raise FileNotFoundError(f"Missing {path}; run scripts/build_final_datasets_package.py first")
    return list(read_jsonl(path))


def source_records(records: list[dict[str, Any]], source: str) -> list[dict[str, Any]]:
    return [record for record in records if record.get("source") == source]


def dataset_overview(single: list[dict[str, Any]], multi_only: list[dict[str, Any]], combined: list[dict[str, Any]]) -> pd.DataFrame:
    rows = []
    for name, records in {
        "final_single_label": single,
        "final_multi_label_only": multi_only,
        "final_combined": combined,
    }.items():
        rows.append(
            {
                "dataset": name,
                "records": len(records),
                "sources": ", ".join(sorted({record["source"] for record in records})),
                "papers_with_code_records": sum(record["source"] == "papers_with_code" for record in records),
                "biotools_records": sum(record["source"] == "bio.tools" for record in records),
                "unique_labels_total": len({label for record in records for label in record["labels"]}),
                "records_with_readme": sum(bool(record.get("readme_content")) for record in records),
                "records_with_somef_description": sum(bool(record.get("somef_description")) for record in records),
                "records_with_title_or_abstract": sum(bool(record.get("paper_title") or record.get("paper_abstract")) for record in records),
            }
        )
    return pd.DataFrame(rows)


def label_distribution(records: list[dict[str, Any]]) -> pd.DataFrame:
    rows = []
    for source in sorted({record["source"] for record in records}):
        counter = Counter(label for record in records if record["source"] == source for label in record["labels"])
        total = sum(counter.values())
        for label, support in counter.most_common():
            rows.append(
                {
                    "source": source,
                    "label": label,
                    "support": support,
                    "percent_of_source_assignments": support / total * 100 if total else 0.0,
                }
            )
    return pd.DataFrame(rows)


def has_any_text(record: dict[str, Any], fields: list[str]) -> bool:
    for field in fields:
        value = record.get(field)
        if isinstance(value, list):
            if any(str(item).strip() for item in value if item is not None):
                return True
        elif value is not None and str(value).strip():
            return True
    return False


def attribute_coverage(records: list[dict[str, Any]]) -> pd.DataFrame:
    rows = []
    for source in sorted({record["source"] for record in records}):
        source_rows = [record for record in records if record["source"] == source]
        for attribute_set, fields in ATTRIBUTE_COMBINATIONS.items():
            texts = [build_text(record, fields) for record in source_rows]
            lengths = [len(text) for text in texts if text]
            count = len(lengths)
            rows.append(
                {
                    "source": source,
                    "attribute_set": attribute_set,
                    "included_fields": ";".join(fields),
                    "excluded_leakage_fields": ";".join(EXCLUDED_LEAKAGE_FIELDS),
                    "records_with_text": count,
                    "records": len(source_rows),
                    "coverage_percent": count / len(source_rows) * 100 if source_rows else 0.0,
                    "mean_text_chars": float(np.mean(lengths)) if lengths else 0.0,
                    "median_text_chars": float(np.median(lengths)) if lengths else 0.0,
                    "empty_predictor_text_records": len(source_rows) - count,
                    "missing_fields_replaced_with_empty_strings": True,
                }
            )
    return pd.DataFrame(rows)


def build_single_dataset(records: list[dict[str, Any]], source: str) -> list[dict[str, Any]]:
    dataset = []
    for record in source_records(records, source):
        labels = clean_list(record.get("labels"))
        if len(labels) == 1:
            row = dict(record)
            row["target"] = labels[0]
            dataset.append(row)
    return dataset


def build_multi_dataset(records: list[dict[str, Any]], source: str) -> list[dict[str, Any]]:
    dataset = []
    for record in source_records(records, source):
        labels = clean_list(record.get("labels"))
        if labels:
            row = dict(record)
            row["target"] = labels
            dataset.append(row)
    return dataset


def all_tasks(single: list[dict[str, Any]], multi_only: list[dict[str, Any]], combined: list[dict[str, Any]]) -> list[tuple[str, str, str, list[dict[str, Any]]]]:
    return [
        ("pwc_single_only", "papers_with_code", "single", build_single_dataset(single, "papers_with_code")),
        ("pwc_multi_only", "papers_with_code", "multi", build_multi_dataset(multi_only, "papers_with_code")),
        ("pwc_merged", "papers_with_code", "multi", build_multi_dataset(combined, "papers_with_code")),
        ("biotools_single_only", "bio.tools", "single", build_single_dataset(single, "bio.tools")),
        ("biotools_multi_only", "bio.tools", "multi", build_multi_dataset(multi_only, "bio.tools")),
        ("biotools_merged", "bio.tools", "multi", build_multi_dataset(combined, "bio.tools")),
    ]


def smoke_sample_records(records: list[dict[str, Any]], label_setting: str, sample_size: int) -> list[dict[str, Any]]:
    """Return a deterministic tiny sample that is still trainable."""
    if sample_size <= 0 or len(records) <= sample_size:
        return records
    if label_setting == "single":
        grouped: dict[str, list[int]] = {}
        for index, record in enumerate(records):
            grouped.setdefault(str(record["target"]), []).append(index)
        labels = sorted(grouped, key=lambda label: (-len(grouped[label]), label.casefold()))
        labels = [label for label in labels if len(grouped[label]) >= 2]
        if len(labels) >= 2:
            selected: list[int] = []
            cursors = {label: 0 for label in labels}
            while len(selected) < sample_size:
                progressed = False
                for label in labels:
                    cursor = cursors[label]
                    if cursor < len(grouped[label]):
                        selected.append(grouped[label][cursor])
                        cursors[label] += 1
                        progressed = True
                    if len(selected) >= sample_size:
                        break
                if not progressed:
                    break
            return [records[index] for index in sorted(selected[:sample_size])]
    return records[:sample_size]


def selected_models(raw: str) -> list[str]:
    aliases = {
        "simple": SIMPLE_MODELS,
        "classical": SIMPLE_MODELS,
        "bert": list(FROZEN_BERT_PIPELINES),
        "local_all": SIMPLE_MODELS + list(FROZEN_BERT_PIPELINES),
        "local_llm": list(LOCAL_LLM_PIPELINES),
        "prompting": list(LOCAL_LLM_PIPELINES),
        "all": SIMPLE_MODELS + list(FROZEN_BERT_PIPELINES) + list(LOCAL_LLM_PIPELINES),
    }
    if raw in aliases:
        return aliases[raw]
    models = [item.strip() for item in raw.split(",") if item.strip()]
    known = set(SIMPLE_MODELS) | set(FROZEN_BERT_PIPELINES) | set(LOCAL_LLM_PIPELINES)
    unknown = [model for model in models if model not in known]
    if unknown:
        raise ValueError(f"Unknown model(s): {', '.join(unknown)}")
    return models


def selected_dataset_names(raw: str, tasks: list[tuple[str, str, str, list[dict[str, Any]]]]) -> set[str]:
    if raw == "all":
        return {task[0] for task in tasks}
    return {item.strip() for item in raw.split(",") if item.strip()}


def selected_attribute_names(raw: str) -> set[str]:
    if raw == "all":
        return set(ATTRIBUTE_COMBINATIONS)
    return {item.strip() for item in raw.split(",") if item.strip()}


def result_key(dataset_name: str, attribute_set: str, model_name: str, split_name: str, fold_id: Any) -> tuple[str, str, str, str, str]:
    fold = "" if fold_id is None or pd.isna(fold_id) else str(int(fold_id) if isinstance(fold_id, float) and fold_id.is_integer() else fold_id)
    return (dataset_name, attribute_set, model_name, split_name, fold)


def load_completed_result_keys(path: Path) -> set[tuple[str, str, str, str, str]]:
    if not path.exists():
        return set()
    existing = safe_read_csv(path)
    required = {"dataset_name", "attribute_set", "model_name", "split_name", "fold_id"}
    if existing.empty or not required.issubset(existing.columns):
        return set()
    if "status" in existing.columns:
        existing = existing[existing["status"].fillna("").eq("completed")]
    return {
        result_key(row.dataset_name, row.attribute_set, row.model_name, row.split_name, row.fold_id)
        for row in existing.itertuples(index=False)
    }


def should_skip_existing_result(args: argparse.Namespace, dataset_name: str, attribute_set: str, model_name: str, split_name: str, fold_id: Any) -> bool:
    if not args.skip_existing_results:
        return False
    existing_keys = getattr(args, "completed_result_keys", set())
    return result_key(dataset_name, attribute_set, model_name, split_name, fold_id) in existing_keys


def make_estimator(model_name: str, label_setting: str, args: argparse.Namespace) -> Any:
    if model_name == "tfidf_logistic_regression":
        estimator: Any = SGDClassifier(
            loss="log_loss",
            penalty="l2",
            alpha=1e-4,
            max_iter=1000,
            tol=1e-3,
            class_weight="balanced",
            random_state=RANDOM_SEED,
            n_jobs=-1,
        )
    elif model_name == "tfidf_linear_svm":
        estimator = LinearSVC(class_weight="balanced", random_state=RANDOM_SEED, max_iter=2500, tol=1e-2)
    elif model_name == "tfidf_random_forest":
        estimator = RandomForestClassifier(
            n_estimators=args.rf_trees,
            class_weight="balanced_subsample",
            n_jobs=-1,
            random_state=RANDOM_SEED,
            max_features="sqrt",
        )
    elif model_name == "tfidf_xgboost":
        if importlib.util.find_spec("xgboost") is None:
            raise RuntimeError("xgboost is not installed")
        estimator = XGBLabelEncodedClassifier(random_state=RANDOM_SEED)
    else:
        raise ValueError(f"Unknown model: {model_name}")
    if label_setting == "multi":
        estimator = OneVsRestClassifier(estimator, n_jobs=1)
    return estimator


def make_embedding_estimator(model_name: str, label_setting: str, args: argparse.Namespace) -> Any:
    spec = FROZEN_BERT_PIPELINES[model_name]
    if spec["classifier"] == "logistic_regression":
        estimator: Any = SGDClassifier(
            loss="log_loss",
            penalty="l2",
            alpha=1e-4,
            max_iter=1000,
            tol=1e-3,
            class_weight="balanced",
            random_state=RANDOM_SEED,
            n_jobs=-1,
        )
    elif spec["classifier"] == "random_forest":
        estimator = RandomForestClassifier(
            n_estimators=args.rf_trees,
            class_weight="balanced_subsample",
            n_jobs=-1,
            random_state=RANDOM_SEED,
            max_features="sqrt",
        )
    else:
        raise ValueError(f"Unsupported embedding classifier: {spec['classifier']}")
    if label_setting == "multi":
        estimator = OneVsRestClassifier(estimator, n_jobs=1)
    return estimator


def make_pipeline(model_name: str, label_setting: str, args: argparse.Namespace) -> Pipeline:
    return Pipeline(
        [
            ("tfidf", TfidfVectorizer(max_features=args.max_features, ngram_range=(1, 2), min_df=2)),
            ("classifier", make_estimator(model_name, label_setting, args)),
        ]
    )


def resolve_embedding_device(args: argparse.Namespace, torch: Any) -> str:
    if args.embedding_device != "auto":
        return args.embedding_device
    return "cuda" if torch.cuda.is_available() else "cpu"


def mean_pool(last_hidden_state: Any, attention_mask: Any, torch: Any) -> Any:
    mask = attention_mask.unsqueeze(-1).expand(last_hidden_state.size()).float()
    masked = last_hidden_state * mask
    summed = masked.sum(dim=1)
    counts = mask.sum(dim=1).clamp(min=1e-9)
    return summed / counts


def embedding_cache_paths(dataset_name: str, attribute_set: str, model_id: str, args: argparse.Namespace) -> tuple[Path, Path]:
    slug = model_slug(model_id)
    stem = f"{dataset_name}__{attribute_set}__{slug}__len{args.embedding_max_length}"
    return EMBEDDINGS_DIR / f"{stem}.npz", EMBEDDINGS_DIR / f"{stem}.json"


def load_or_compute_embeddings(
    texts: list[str],
    dataset_name: str,
    attribute_set: str,
    model_id: str,
    args: argparse.Namespace,
) -> np.ndarray:
    text_hash = stable_json_hash(texts)
    npz_path, metadata_path = embedding_cache_paths(dataset_name, attribute_set, model_id, args)
    if npz_path.exists() and metadata_path.exists():
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        if (
            metadata.get("text_sha256") == text_hash
            and metadata.get("hf_model_id") == model_id
            and metadata.get("embedding_max_length") == args.embedding_max_length
        ):
            LOGGER.info("Loading cached embeddings: %s", npz_path)
            return np.load(npz_path)["embeddings"]

    if importlib.util.find_spec("torch") is None or importlib.util.find_spec("transformers") is None:
        raise RuntimeError("Frozen BERT embeddings need torch and transformers installed")

    import torch
    from transformers import AutoModel, AutoTokenizer

    torch.manual_seed(RANDOM_SEED)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(RANDOM_SEED)
    device = resolve_embedding_device(args, torch)
    LOGGER.info("Computing embeddings with %s on %s for %s/%s", model_id, device, dataset_name, attribute_set)
    tokenizer = AutoTokenizer.from_pretrained(model_id, local_files_only=args.offline_models_only, trust_remote_code=args.trust_remote_code)
    model = AutoModel.from_pretrained(model_id, local_files_only=args.offline_models_only, trust_remote_code=args.trust_remote_code)
    model.to(device)
    model.eval()

    rows: list[np.ndarray] = []
    total_batches = int(np.ceil(len(texts) / args.embedding_batch_size)) if texts else 0
    with torch.no_grad():
        for batch_number, start in enumerate(range(0, len(texts), args.embedding_batch_size), start=1):
            batch = [text if text else " " for text in texts[start : start + args.embedding_batch_size]]
            encoded = tokenizer(
                batch,
                padding=True,
                truncation=True,
                max_length=args.embedding_max_length,
                return_tensors="pt",
            )
            encoded = {key: value.to(device) for key, value in encoded.items()}
            output = model(**encoded)
            pooled = mean_pool(output.last_hidden_state, encoded["attention_mask"], torch)
            rows.append(pooled.detach().cpu().numpy().astype("float32"))
            if args.embedding_progress_every and (batch_number == 1 or batch_number % args.embedding_progress_every == 0 or batch_number == total_batches):
                LOGGER.info(
                    "Embedding progress with %s for %s/%s: batch %s/%s (%s/%s records)",
                    model_id,
                    dataset_name,
                    attribute_set,
                    f"{batch_number:,}",
                    f"{total_batches:,}",
                    f"{min(start + args.embedding_batch_size, len(texts)):,}",
                    f"{len(texts):,}",
                )

    embeddings = np.vstack(rows) if rows else np.empty((0, 0), dtype="float32")
    np.savez_compressed(npz_path, embeddings=embeddings)
    metadata = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "dataset_name": dataset_name,
        "attribute_set": attribute_set,
        "hf_model_id": model_id,
        "num_records": len(texts),
        "text_sha256": text_hash,
        "embedding_shape": list(embeddings.shape),
        "embedding_pooling": "attention_masked_mean_pooling",
        "embedding_max_length": args.embedding_max_length,
        "embedding_batch_size": args.embedding_batch_size,
        "embedding_progress_every": args.embedding_progress_every,
        "embedding_device": device,
        "offline_models_only": args.offline_models_only,
        "trust_remote_code": args.trust_remote_code,
        "random_seed": RANDOM_SEED,
        "package_versions": package_versions(),
    }
    metadata_path.write_text(json.dumps(metadata, indent=2, sort_keys=True), encoding="utf-8")
    LOGGER.info("Saved embeddings: %s", npz_path)
    return embeddings


def split_indices(records: list[dict[str, Any]], label_setting: str) -> tuple[np.ndarray, np.ndarray, str]:
    indices = np.arange(len(records))
    split_note = "deterministic_random_split"
    stratify = None
    if label_setting == "single":
        y = np.array([record["target"] for record in records])
        counts = Counter(y)
        if min(counts.values()) >= 2:
            stratify = y
            split_note = "deterministic_stratified_split"
    train_idx, test_idx = train_test_split(indices, test_size=TEST_SIZE, random_state=RANDOM_SEED, stratify=stratify)
    return train_idx, test_idx, split_note


def cv_splits(records: list[dict[str, Any]], label_setting: str, folds: int) -> list[tuple[np.ndarray, np.ndarray, str]]:
    indices = np.arange(len(records))
    if folds < 2:
        return []
    if label_setting == "single":
        y = np.array([record["target"] for record in records])
        counts = Counter(y)
        if min(counts.values()) >= folds:
            splitter = StratifiedKFold(n_splits=folds, shuffle=True, random_state=RANDOM_SEED)
            return [(train, test, "deterministic_stratified_cv") for train, test in splitter.split(indices, y)]
    splitter = KFold(n_splits=folds, shuffle=True, random_state=RANDOM_SEED)
    return [(train, test, "deterministic_random_cv") for train, test in splitter.split(indices)]


def minimum_records(args: argparse.Namespace) -> int:
    if args.smoke_test_records:
        return max(2, min(MIN_RECORDS, args.smoke_test_records))
    return MIN_RECORDS


def single_metrics(y_true: list[str], y_pred: list[str]) -> dict[str, float]:
    return {
        "accuracy": accuracy_score(y_true, y_pred),
        "balanced_accuracy": balanced_accuracy_score(y_true, y_pred),
        "precision_macro": precision_score(y_true, y_pred, average="macro", zero_division=0),
        "recall_macro": recall_score(y_true, y_pred, average="macro", zero_division=0),
        "f1_micro": f1_score(y_true, y_pred, average="micro", zero_division=0),
        "f1_macro": f1_score(y_true, y_pred, average="macro", zero_division=0),
        "f1_weighted": f1_score(y_true, y_pred, average="weighted", zero_division=0),
    }


def multi_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> dict[str, float]:
    return {
        "subset_accuracy": accuracy_score(y_true, y_pred),
        "hamming_loss": hamming_loss(y_true, y_pred),
        "precision_macro": precision_score(y_true, y_pred, average="macro", zero_division=0),
        "recall_macro": recall_score(y_true, y_pred, average="macro", zero_division=0),
        "f1_micro": f1_score(y_true, y_pred, average="micro", zero_division=0),
        "f1_macro": f1_score(y_true, y_pred, average="macro", zero_division=0),
        "f1_weighted": f1_score(y_true, y_pred, average="weighted", zero_division=0),
        "f1_samples": f1_score(y_true, y_pred, average="samples", zero_division=0),
    }


def per_class_rows(y_true: Any, y_pred: Any, labels: list[str], metadata: dict[str, Any]) -> list[dict[str, Any]]:
    precision, recall, f1, support = precision_recall_fscore_support(y_true, y_pred, labels=labels if metadata["label_setting"] == "single" else None, zero_division=0)
    return [
        {
            **metadata,
            "label": label,
            "precision": precision[pos],
            "recall": recall[pos],
            "f1": f1[pos],
            "support": support[pos],
        }
        for pos, label in enumerate(labels)
    ]


def truncate_text(value: Any, max_chars: int) -> str:
    text = build_text({"value": value}, ["value"]) if not isinstance(value, str) else value
    text = " ".join(text.split())
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 18].rstrip() + " [TRUNCATED]"


def prompt_metadata_payload(record: dict[str, Any], fields: list[str], max_chars: int) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "source": record.get("source"),
        "item_id": record.get("item_id"),
    }
    remaining = max_chars
    for field in fields:
        if remaining <= 0:
            break
        value = record.get(field)
        text = truncate_text(value, remaining)
        if text:
            payload[field] = text
            remaining -= len(field) + len(text)
    return payload


def deterministic_few_shot_examples(
    records: list[dict[str, Any]],
    train_idx: np.ndarray,
    fields: list[str],
    label_setting: str,
    count: int,
    max_chars: int,
) -> list[dict[str, Any]]:
    if count <= 0:
        return []
    examples = []
    seen_signatures: set[str] = set()
    for index in train_idx.tolist():
        record = records[index]
        labels = clean_list(record["target"]) if label_setting == "multi" else [record["target"]]
        signature = "|".join(labels)
        if signature in seen_signatures and len(seen_signatures) < count:
            continue
        seen_signatures.add(signature)
        examples.append(
            {
                "metadata": prompt_metadata_payload(record, fields, max_chars),
                "labels": labels,
            }
        )
        if len(examples) >= count:
            break
    return examples


def render_local_llm_prompt(
    template: str,
    labels: list[str],
    metadata: dict[str, Any],
    label_setting: str,
    examples: list[dict[str, Any]],
) -> str:
    examples_text = "None."
    if examples:
        examples_text = json.dumps(examples, ensure_ascii=False, indent=2, sort_keys=True)
    return (
        template.replace("{labels_json}", json.dumps(labels, ensure_ascii=False, indent=2))
        .replace("{label_setting}", label_setting)
        .replace("{metadata_json}", json.dumps(metadata, ensure_ascii=False, indent=2, sort_keys=True))
        .replace("{examples_json}", examples_text)
    )


def normalize_prompt_labels(raw_labels: Any, allowed_labels: list[str], label_setting: str) -> list[str]:
    allowed_lookup = {label.casefold(): label for label in allowed_labels}
    labels = []
    if isinstance(raw_labels, str):
        raw_iterable = [raw_labels]
    elif isinstance(raw_labels, list):
        raw_iterable = raw_labels
    else:
        raw_iterable = []
    for raw_label in raw_iterable:
        label = allowed_lookup.get(str(raw_label).strip().casefold())
        if label and label not in labels:
            labels.append(label)
    if label_setting == "single":
        return labels[:1]
    return labels


def parse_local_llm_json(text: str) -> dict[str, Any]:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            return json.loads(text[start : end + 1])
        raise


def call_local_llm_classifier(
    prompt: str,
    labels: list[str],
    label_setting: str,
    model_name: str,
    args: argparse.Namespace,
) -> dict[str, Any]:
    cache_key = stable_json_hash(
        {
            "provider": "local_llm",
            "model": args.local_llm_model,
            "pipeline": model_name,
            "temperature": args.local_llm_temperature,
            "prompt": prompt,
            "labels": labels,
            "label_setting": label_setting,
        }
    )
    cache_path = LOCAL_LLM_CACHE_DIR / f"{cache_key}.json"
    conversation_path = LOCAL_LLM_CONVERSATIONS_DIR / f"{cache_key}.json"
    if cache_path.exists():
        return json.loads(cache_path.read_text(encoding="utf-8"))

    if not args.enable_local_llm:
        raise RuntimeError("Local LLM model selected but --enable-local-llm was not passed")
    if args.local_llm_model == "XXX_LOCAL_LLM_MODEL":
        raise RuntimeError("Set --local-llm-model to the exact local instruction-tuned model identifier before running prompts")
    if not args.local_llm_command:
        raise RuntimeError("Set --local-llm-command to a local runtime command that reads prompts from stdin and returns JSON")

    command = shlex.split(args.local_llm_command)
    if not command:
        raise RuntimeError("--local-llm-command did not contain an executable command")

    attempts: list[dict[str, Any]] = []
    content = ""
    parsed: dict[str, Any] | None = None
    for attempt in range(args.local_llm_max_retries + 1):
        started_at = datetime.now().isoformat(timespec="seconds")
        completed = subprocess.run(
            command,
            input=prompt,
            text=True,
            capture_output=True,
            timeout=args.local_llm_timeout,
            check=False,
        )
        content = completed.stdout.strip()
        attempt_row = {
            "attempt": attempt + 1,
            "started_at": started_at,
            "returncode": completed.returncode,
            "stdout": content,
            "stderr": completed.stderr.strip(),
        }
        try:
            candidate = parse_local_llm_json(content)
            normalized = normalize_prompt_labels(candidate.get("labels"), labels, label_setting)
            if label_setting == "single" and len(normalized) != 1:
                raise ValueError("single-label prompts must return exactly one allowed label")
            candidate["labels"] = normalized
            parsed = candidate
            attempt_row["parsed"] = True
        except Exception as exc:  # noqa: BLE001 - parser failures are recorded for audit.
            attempt_row["parsed"] = False
            attempt_row["parse_error"] = str(exc)
        attempts.append(attempt_row)
        if parsed is not None:
            break
        if args.local_llm_sleep_seconds:
            time.sleep(args.local_llm_sleep_seconds)

    if parsed is None:
        raise RuntimeError("Local LLM did not return valid structured JSON after retries")

    conversation = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "cache_key": cache_key,
        "provider": "local_llm",
        "local_llm_model": args.local_llm_model,
        "pipeline": model_name,
        "label_setting": label_setting,
        "temperature": args.local_llm_temperature,
        "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
        "labels": labels,
        "prompt": prompt,
        "attempts": attempts,
        "parsed_response": parsed,
    }
    row = {
        "generated_at": conversation["generated_at"],
        "cache_key": cache_key,
        "local_llm_model": args.local_llm_model,
        "pipeline": model_name,
        "label_setting": label_setting,
        "prompt_sha256": conversation["prompt_sha256"],
        "conversation_path": str(conversation_path.relative_to(FINAL_RESULTS_DIR)),
        "response_text": json.dumps(parsed, ensure_ascii=False, sort_keys=True),
        "raw_response_text": content,
        "parse_attempts": len(attempts),
        "invalid_response_count": sum(1 for attempt in attempts if not attempt.get("parsed")),
    }
    conversation_path.write_text(json.dumps(conversation, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    cache_path.write_text(json.dumps(row, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    if args.local_llm_sleep_seconds:
        time.sleep(args.local_llm_sleep_seconds)
    return row


def parsed_local_llm_prediction(cache_row: dict[str, Any], allowed_labels: list[str], label_setting: str) -> dict[str, Any]:
    try:
        parsed = json.loads(cache_row.get("response_text") or "{}")
    except json.JSONDecodeError:
        parsed = {}
    labels = normalize_prompt_labels(parsed.get("labels"), allowed_labels, label_setting)
    return {
        "labels": labels,
        "confidence": parsed.get("confidence"),
        "evidence": parsed.get("evidence") if isinstance(parsed.get("evidence"), list) else [],
        "abstain": bool(parsed.get("abstain", False)),
        "local_llm_cache_key": cache_row.get("cache_key"),
        "local_llm_conversation_path": cache_row.get("conversation_path"),
        "prompt_sha256": cache_row.get("prompt_sha256"),
        "response_text": cache_row.get("response_text"),
        "raw_response_text": cache_row.get("raw_response_text"),
        "parse_attempts": cache_row.get("parse_attempts"),
        "invalid_response_count": cache_row.get("invalid_response_count"),
    }


def write_split(dataset_name: str, train_idx: np.ndarray, test_idx: np.ndarray) -> None:
    path = SPLITS_DIR / f"{dataset_name}_train_test_split.json"
    path.write_text(json.dumps({"train_indices": train_idx.tolist(), "test_indices": test_idx.tolist(), "random_seed": RANDOM_SEED}, indent=2), encoding="utf-8")


def hard_vote(predictions: list[Any], label_setting: str) -> Any:
    if label_setting == "single":
        voted = []
        for row_values in zip(*predictions):
            voted.append(Counter(row_values).most_common(1)[0][0])
        return voted
    stacked = np.stack(predictions, axis=0)
    return (stacked.sum(axis=0) >= ((len(predictions) / 2) + 0.0001)).astype(int)


def add_completed_rows(
    summary_rows: list[dict[str, Any]],
    prediction_rows: list[dict[str, Any]],
    per_label_rows: list[dict[str, Any]],
    records: list[dict[str, Any]],
    test_idx: np.ndarray,
    metadata: dict[str, Any],
    label_setting: str,
    y_test: Any,
    y_pred: Any,
    class_labels: list[str],
    mlb: MultiLabelBinarizer | None = None,
    extra_predictions: list[dict[str, Any]] | None = None,
) -> None:
    metrics = single_metrics(y_test, list(y_pred)) if label_setting == "single" else multi_metrics(y_test, y_pred)
    summary_rows.append({**metadata, "status": "completed", **metrics})
    per_label_rows.extend(per_class_rows(y_test, y_pred, class_labels, metadata))
    if metadata["split_name"] != "train_test":
        return
    extra_predictions = extra_predictions or [{} for _ in test_idx]
    if label_setting == "single":
        prediction_rows.extend(
            {
                **metadata,
                "record_id": records[index].get("item_id"),
                "true_label": y_test[pos],
                "predicted_label": y_pred[pos],
                **extra_predictions[pos],
            }
            for pos, index in enumerate(test_idx)
        )
    else:
        if mlb is None:
            raise ValueError("Multi-label predictions require a fitted MultiLabelBinarizer")
        true_labels = list(mlb.inverse_transform(y_test))
        pred_labels = list(mlb.inverse_transform(y_pred))
        prediction_rows.extend(
            {
                **metadata,
                "record_id": records[index].get("item_id"),
                "true_label": list(true_labels[pos]),
                "predicted_label": list(pred_labels[pos]),
                **extra_predictions[pos],
            }
            for pos, index in enumerate(test_idx)
        )


def evaluate_local_llm_split(
    records: list[dict[str, Any]],
    fields: list[str],
    train_idx: np.ndarray,
    test_idx: np.ndarray,
    model_name: str,
    metadata: dict[str, Any],
    label_setting: str,
    class_labels: list[str],
    y_test: Any,
    args: argparse.Namespace,
) -> tuple[Any, list[dict[str, Any]]]:
    if metadata["split_name"] == "cv" and not args.local_llm_on_cv:
        raise RuntimeError("Local LLM prompting on CV folds is disabled; pass --local-llm-on-cv to run it")
    template = LOCAL_LLM_PROMPT_TEMPLATE.read_text(encoding="utf-8")
    example_count = 0
    if model_name == "local_llm_one_shot":
        example_count = 1
    elif model_name == "local_llm_few_shot":
        example_count = args.local_llm_few_shot_examples
    examples = []
    if example_count:
        examples = deterministic_few_shot_examples(
            records,
            train_idx,
            fields,
            label_setting,
            example_count,
            args.local_llm_max_metadata_chars,
        )
    predictions: list[list[str]] = []
    extra_rows: list[dict[str, Any]] = []
    for index in test_idx.tolist():
        metadata_payload = prompt_metadata_payload(records[index], fields, args.local_llm_max_metadata_chars)
        prompt = render_local_llm_prompt(template, class_labels, metadata_payload, label_setting, examples)
        cache_row = call_local_llm_classifier(prompt, class_labels, label_setting, model_name, args)
        parsed = parsed_local_llm_prediction(cache_row, class_labels, label_setting)
        predictions.append(parsed["labels"])
        extra_rows.append(
            {
                "local_llm_model": args.local_llm_model,
                "local_llm_cache_key": parsed["local_llm_cache_key"],
                "local_llm_conversation_path": parsed["local_llm_conversation_path"],
                "prompt_sha256": parsed["prompt_sha256"],
                "local_llm_confidence": parsed["confidence"],
                "local_llm_evidence": parsed["evidence"],
                "local_llm_abstain": parsed["abstain"],
                "local_llm_parse_attempts": parsed["parse_attempts"],
                "local_llm_invalid_response_count": parsed["invalid_response_count"],
                "response_text": parsed["response_text"],
                "raw_response_text": parsed["raw_response_text"],
            }
        )
    if label_setting == "single":
        y_pred = [labels[0] if labels else NO_PREDICTION_LABEL for labels in predictions]
    else:
        label_to_pos = {label: pos for pos, label in enumerate(class_labels)}
        y_pred = np.zeros((len(predictions), len(class_labels)), dtype=int)
        for row_pos, labels in enumerate(predictions):
            for label in labels:
                if label in label_to_pos:
                    y_pred[row_pos, label_to_pos[label]] = 1
    return y_pred, extra_rows


def evaluate_one_split(
    records: list[dict[str, Any]],
    dataset_name: str,
    source: str,
    label_setting: str,
    attribute_set: str,
    fields: list[str],
    train_idx: np.ndarray,
    test_idx: np.ndarray,
    split_note: str,
    split_name: str,
    fold_id: int | None,
    models: list[str],
    args: argparse.Namespace,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    summary_rows: list[dict[str, Any]] = []
    prediction_rows: list[dict[str, Any]] = []
    per_label_rows: list[dict[str, Any]] = []
    texts = [build_text(record, fields) for record in records]
    if sum(bool(text) for text in texts) < minimum_records(args):
        return summary_rows, prediction_rows, per_label_rows

    num_labels = len({label for record in records for label in clean_list(record["target"])}) if label_setting == "multi" else len({record["target"] for record in records})
    x_train = [texts[index] for index in train_idx]
    x_test = [texts[index] for index in test_idx]
    base_metadata = {
        "source_dataset": source,
        "label_setting": label_setting,
        "dataset_name": dataset_name,
        "num_records": len(records),
        "num_train": len(train_idx),
        "num_test": len(test_idx),
        "num_labels": num_labels,
        "attribute_set": attribute_set,
        "split": split_note,
        "split_name": split_name,
        "fold_id": fold_id,
        "random_seed": RANDOM_SEED,
        "is_smoke_test": bool(args.smoke_test_records),
        "smoke_test_records": args.smoke_test_records or "",
    }

    fitted_predictions: dict[str, Any] = {}
    if label_setting == "single":
        y = [record["target"] for record in records]
        y_train = [y[index] for index in train_idx]
        y_test = [y[index] for index in test_idx]
        class_labels = sorted(set(y))
    else:
        mlb = MultiLabelBinarizer()
        y_all = mlb.fit_transform([record["target"] for record in records])
        y_train = y_all[train_idx]
        y_test = y_all[test_idx]
        class_labels = list(mlb.classes_)

    vote_members = ["tfidf_logistic_regression", "tfidf_linear_svm", "tfidf_random_forest"]
    hard_voting_requested = "tfidf_hard_voting" in models
    hard_voting_already_completed = should_skip_existing_result(args, dataset_name, attribute_set, "tfidf_hard_voting", split_name, fold_id)
    need_vote_member_predictions = hard_voting_requested and not hard_voting_already_completed

    for model_name in [model for model in models if model != "tfidf_hard_voting"]:
        metadata = {**base_metadata, "model_name": model_name}
        skip_completed_row = should_skip_existing_result(args, dataset_name, attribute_set, model_name, split_name, fold_id)
        compute_for_hard_vote = need_vote_member_predictions and model_name in vote_members
        if skip_completed_row and not compute_for_hard_vote:
            LOGGER.info("Skipping existing completed result %s | %s | %s | %s", dataset_name, attribute_set, model_name, split_name)
            continue
        try:
            if model_name in SIMPLE_MODELS:
                pipeline = make_pipeline(model_name, label_setting, args)
                with warnings.catch_warnings():
                    warnings.filterwarnings("ignore", category=ConvergenceWarning)
                    pipeline.fit(x_train, y_train)
                y_pred = pipeline.predict(x_test)
                fitted_predictions[model_name] = y_pred
                if not skip_completed_row:
                    add_completed_rows(
                        summary_rows,
                        prediction_rows,
                        per_label_rows,
                        records,
                        test_idx,
                        metadata,
                        label_setting,
                        y_test,
                        y_pred,
                        class_labels,
                        mlb if label_setting == "multi" else None,
                    )
            elif model_name in FROZEN_BERT_PIPELINES:
                spec = FROZEN_BERT_PIPELINES[model_name]
                embeddings = load_or_compute_embeddings(texts, dataset_name, attribute_set, spec["hf_model_id"], args)
                estimator = make_embedding_estimator(model_name, label_setting, args)
                with warnings.catch_warnings():
                    warnings.filterwarnings("ignore", category=ConvergenceWarning)
                    estimator.fit(embeddings[train_idx], y_train)
                y_pred = estimator.predict(embeddings[test_idx])
                if not skip_completed_row:
                    add_completed_rows(
                        summary_rows,
                        prediction_rows,
                        per_label_rows,
                        records,
                        test_idx,
                        {**metadata, "hf_model_id": spec["hf_model_id"], "embedding_pooling": "attention_masked_mean_pooling"},
                        label_setting,
                        y_test,
                        y_pred,
                        class_labels,
                        mlb if label_setting == "multi" else None,
                    )
            elif model_name in LOCAL_LLM_PIPELINES:
                y_pred, extra_rows = evaluate_local_llm_split(
                    records,
                    fields,
                    train_idx,
                    test_idx,
                    model_name,
                    metadata,
                    label_setting,
                    class_labels,
                    y_test,
                    args,
                )
                if not skip_completed_row:
                    add_completed_rows(
                        summary_rows,
                        prediction_rows,
                        per_label_rows,
                        records,
                        test_idx,
                        {**metadata, "local_llm_model": args.local_llm_model, "prompt_template": str(LOCAL_LLM_PROMPT_TEMPLATE.relative_to(ROOT))},
                        label_setting,
                        y_test,
                        y_pred,
                        class_labels,
                        mlb if label_setting == "multi" else None,
                        extra_rows,
                    )
            else:
                raise ValueError(f"Unknown model: {model_name}")
        except Exception as exc:  # noqa: BLE001 - experiment runners should report failures, not stop the full batch.
            status = "failed"
            if model_name in LOCAL_LLM_PIPELINES and (
                not args.enable_local_llm
                or "CV folds is disabled" in str(exc)
                or "XXX_LOCAL_LLM_MODEL" in str(exc)
                or "--local-llm-command" in str(exc)
            ):
                status = "not_run"
            summary_rows.append({**metadata, "status": status, "skip_reason": str(exc)})
            continue
        if skip_completed_row:
            LOGGER.info("Computed %s | %s | %s | %s for missing hard-voting result only", dataset_name, attribute_set, model_name, split_name)
        else:
            LOGGER.info("Completed %s | %s | %s | %s", dataset_name, attribute_set, model_name, split_name)

    if hard_voting_requested and hard_voting_already_completed:
        LOGGER.info("Skipping existing completed result %s | %s | tfidf_hard_voting | %s", dataset_name, attribute_set, split_name)
    elif hard_voting_requested and all(member in fitted_predictions for member in vote_members):
        metadata = {**base_metadata, "model_name": "tfidf_hard_voting"}
        y_pred = hard_vote([fitted_predictions[member] for member in vote_members], label_setting)
        add_completed_rows(
            summary_rows,
            prediction_rows,
            per_label_rows,
            records,
            test_idx,
            metadata,
            label_setting,
            y_test,
            y_pred,
            class_labels,
            mlb if label_setting == "multi" else None,
        )

    return summary_rows, prediction_rows, per_label_rows


def evaluate_dataset(
    records: list[dict[str, Any]],
    dataset_name: str,
    source: str,
    label_setting: str,
    models: list[str],
    args: argparse.Namespace,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    summary_rows: list[dict[str, Any]] = []
    prediction_rows: list[dict[str, Any]] = []
    per_label_rows: list[dict[str, Any]] = []
    if len(records) < minimum_records(args):
        return summary_rows, prediction_rows, per_label_rows

    train_idx, test_idx, split_note = split_indices(records, label_setting)
    write_split(dataset_name, train_idx, test_idx)
    splits = [(train_idx, test_idx, split_note, "train_test", None)]
    splits.extend((train, test, note, "cv", fold_id) for fold_id, (train, test, note) in enumerate(cv_splits(records, label_setting, args.folds), start=1))

    wanted_attributes = selected_attribute_names(args.attributes)
    for attribute_set, fields in ATTRIBUTE_COMBINATIONS.items():
        if attribute_set not in wanted_attributes:
            continue
        for train, test, note, split_name, fold_id in splits:
            summary, predictions, per_class = evaluate_one_split(
                records,
                dataset_name,
                source,
                label_setting,
                attribute_set,
                fields,
                train,
                test,
                note,
                split_name,
                fold_id,
                models,
                args,
            )
            summary_rows.extend(summary)
            prediction_rows.extend(predictions)
            per_label_rows.extend(per_class)
    return summary_rows, prediction_rows, per_label_rows


def cv_summary(classification: pd.DataFrame) -> pd.DataFrame:
    cv = classification[classification["split_name"].eq("cv") & classification["status"].eq("completed")].copy()
    if cv.empty:
        return pd.DataFrame()
    metric_cols = [col for col in ["accuracy", "balanced_accuracy", "subset_accuracy", "hamming_loss", "f1_micro", "f1_macro", "f1_weighted", "f1_samples"] if col in cv.columns]
    grouped = cv.groupby(["dataset_name", "label_setting", "attribute_set", "model_name"], dropna=False)[metric_cols]
    rows = []
    for keys, group in grouped:
        row = dict(zip(["dataset_name", "label_setting", "attribute_set", "model_name"], keys))
        row["folds"] = len(group)
        for col in metric_cols:
            row[f"{col}_mean"] = group[col].mean()
            row[f"{col}_std"] = group[col].std(ddof=1) if len(group) > 1 else 0.0
        rows.append(row)
    return pd.DataFrame(rows)


def skipped_experiments(tasks: list[tuple[str, str, str, list[dict[str, Any]]]], include_heavy: bool) -> pd.DataFrame:
    rows = []
    if include_heavy:
        deps = {
            "sentence_transformers": bool(importlib.util.find_spec("sentence_transformers")),
            "transformers": bool(importlib.util.find_spec("transformers")),
            "torch": bool(importlib.util.find_spec("torch")),
        }
        for dataset_name, source, label_setting, _records in tasks:
            for model_name, reason in HEAVY_PIPELINES:
                rows.append(
                    {
                        "dataset_name": dataset_name,
                        "source_dataset": source,
                        "label_setting": label_setting,
                        "model_name": model_name,
                        "status": "not_run",
                        "reason": reason,
                        "sentence_transformers_installed": deps["sentence_transformers"],
                        "transformers_installed": deps["transformers"],
                        "torch_installed": deps["torch"],
                        "local_llm_command_configured": bool(os.environ.get("LOCAL_LLM_COMMAND")),
                    }
                )
    return pd.DataFrame(rows)


def model_metadata_rows(args: argparse.Namespace) -> list[dict[str, Any]]:
    selected = set(selected_models(args.models))
    rows: list[dict[str, Any]] = []
    for model_name in SIMPLE_MODELS:
        rows.append(
            {
                "model_name": model_name,
                "family": "tfidf_simple",
                "selected": model_name in selected,
                "feature_extractor": "TfidfVectorizer",
                "hf_model_id": "",
                "classifier": model_name.replace("tfidf_", ""),
                "transformer_weights_updated": False,
                "remote_api": False,
                "random_seed": RANDOM_SEED,
                "notes": "Simple local baseline; random forest is included in the default simple/classical set.",
            }
        )
    for model_name, spec in FROZEN_BERT_PIPELINES.items():
        rows.append(
            {
                "model_name": model_name,
                "family": spec["family"],
                "selected": model_name in selected,
                "feature_extractor": "AutoModel attention-masked mean pooling",
                "hf_model_id": spec["hf_model_id"],
                "classifier": spec["classifier"],
                "transformer_weights_updated": False,
                "remote_api": False,
                "random_seed": RANDOM_SEED,
                "notes": spec["description"],
            }
        )
    for model_name, spec in LOCAL_LLM_PIPELINES.items():
        rows.append(
            {
                "model_name": model_name,
                "family": spec["family"],
                "selected": model_name in selected,
                "feature_extractor": "prompted structured-output classification",
                "hf_model_id": "",
                "classifier": args.local_llm_model,
                "transformer_weights_updated": False,
                "remote_api": False,
                "random_seed": RANDOM_SEED,
                "notes": spec["description"],
            }
        )
    return rows


def merge_existing_table(path: Path, new_df: pd.DataFrame, keys: list[str]) -> pd.DataFrame:
    if not path.exists():
        return new_df
    if path.suffix == ".jsonl":
        try:
            existing = pd.read_json(path, orient="records", lines=True)
        except ValueError:
            existing = pd.DataFrame()
    else:
        existing = safe_read_csv(path)
    if new_df.empty:
        return existing
    if existing.empty:
        return new_df
    shared_keys = [key for key in keys if key in existing.columns and key in new_df.columns]
    if not shared_keys:
        return pd.concat([existing, new_df], ignore_index=True)
    def key_value(value: Any) -> str:
        return "" if pd.isna(value) else str(value)

    existing_cmp = existing[shared_keys].apply(lambda row: "||".join(key_value(value) for value in row.tolist()), axis=1)
    new_cmp = set(new_df[shared_keys].apply(lambda row: "||".join(key_value(value) for value in row.tolist()), axis=1))
    retained = existing[~existing_cmp.isin(new_cmp)]
    return pd.concat([retained, new_df], ignore_index=True)


def run_training(single: list[dict[str, Any]], multi_only: list[dict[str, Any]], combined: list[dict[str, Any]], args: argparse.Namespace) -> pd.DataFrame:
    all_summary: list[dict[str, Any]] = []
    all_predictions: list[dict[str, Any]] = []
    all_per_class: list[dict[str, Any]] = []
    tasks = all_tasks(single, multi_only, combined)
    wanted_datasets = selected_dataset_names(args.datasets, tasks)
    models = selected_models(args.models)
    if args.skip_existing_results:
        args.completed_result_keys = load_completed_result_keys(TABLES_DIR / "classification_results.csv")
        LOGGER.info("Loaded %s existing completed result keys to skip", f"{len(args.completed_result_keys):,}")
    else:
        args.completed_result_keys = set()
    for dataset_name, source, label_setting, records in tasks:
        if dataset_name not in wanted_datasets:
            continue
        if args.smoke_test_records:
            original_count = len(records)
            records = smoke_sample_records(records, label_setting, args.smoke_test_records)
            LOGGER.info("Smoke-test sample for %s: %s of %s records", dataset_name, f"{len(records):,}", f"{original_count:,}")
        LOGGER.info("Training %s with %s records using %s", dataset_name, f"{len(records):,}", ", ".join(models))
        summary, predictions, per_class = evaluate_dataset(records, dataset_name, source, label_setting, models, args)
        all_summary.extend(summary)
        all_predictions.extend(predictions)
        all_per_class.extend(per_class)
    prediction_df = pd.DataFrame(all_predictions)
    if args.append_results:
        prediction_df = merge_existing_table(
            PREDICTIONS_DIR / "predictions.jsonl",
            prediction_df,
            ["dataset_name", "attribute_set", "model_name", "split_name", "fold_id", "record_id"],
        )
    prediction_df.to_json(PREDICTIONS_DIR / "predictions.jsonl", orient="records", lines=True, force_ascii=False)
    LOGGER.info("Wrote predictions")
    per_class_df = pd.DataFrame(all_per_class)
    if args.append_results:
        per_class_df = merge_existing_table(
            TABLES_DIR / "per_class_results.csv",
            per_class_df,
            ["dataset_name", "attribute_set", "model_name", "split_name", "fold_id", "label"],
        )
    per_class_df.to_csv(TABLES_DIR / "per_class_results.csv", index=False)
    LOGGER.info("Wrote per-class results")
    skipped = skipped_experiments(tasks, args.include_heavy_skipped)
    skipped.to_csv(TABLES_DIR / "skipped_experiments.csv", index=False)
    LOGGER.info("Wrote skipped experiment table")
    summary_df = pd.DataFrame(all_summary)
    if args.append_results:
        summary_df = merge_existing_table(
            TABLES_DIR / "classification_results.csv",
            summary_df,
            ["dataset_name", "attribute_set", "model_name", "split_name", "fold_id"],
        )
    summary_df.to_csv(TABLES_DIR / "classification_results.csv", index=False)
    LOGGER.info("Wrote classification results")
    cv_summary(summary_df).to_csv(TABLES_DIR / "cv_summary.csv", index=False)
    LOGGER.info("Wrote CV summary")
    return summary_df


def save_tables(single: list[dict[str, Any]], multi_only: list[dict[str, Any]], combined: list[dict[str, Any]], classification: pd.DataFrame, args: argparse.Namespace) -> dict[str, pd.DataFrame]:
    tables = {
        "dataset_overview": dataset_overview(single, multi_only, combined),
        "label_distribution": label_distribution(combined),
        "attribute_coverage": attribute_coverage(combined),
        "classification_results": classification,
        "model_metadata": pd.DataFrame(model_metadata_rows(args)),
    }
    per_class_path = TABLES_DIR / "per_class_results.csv"
    skipped_path = TABLES_DIR / "skipped_experiments.csv"
    cv_path = TABLES_DIR / "cv_summary.csv"
    if per_class_path.exists():
        tables["per_class_results"] = safe_read_csv(per_class_path)
    if skipped_path.exists():
        tables["skipped_experiments"] = safe_read_csv(skipped_path)
    if cv_path.exists():
        tables["cv_summary"] = safe_read_csv(cv_path)
    if not classification.empty and "f1_macro" in classification.columns:
        completed = classification[classification.get("status", "completed").eq("completed") if "status" in classification.columns else classification.index == classification.index]
        best = completed[completed["split_name"].eq("train_test")] if "split_name" in completed.columns else completed
        tables["best_attribute_results"] = best.sort_values("f1_macro", ascending=False).groupby(["dataset_name", "label_setting"], as_index=False).head(5)
    for name, table in tables.items():
        table.to_csv(TABLES_DIR / f"{name}.csv", index=False)
    LOGGER.info("Wrote CSV tables")
    with pd.ExcelWriter(TABLES_DIR / "final_analysis_tables.xlsx") as writer:
        for name, table in tables.items():
            table.to_excel(writer, sheet_name=name[:31], index=False)
    LOGGER.info("Wrote Excel workbook")
    return tables


def safe_read_csv(path: Path) -> pd.DataFrame:
    try:
        return pd.read_csv(path)
    except pd.errors.EmptyDataError:
        return pd.DataFrame()


def save_figures(tables: dict[str, pd.DataFrame]) -> None:
    plt.rcParams.update({"axes.grid": True, "grid.alpha": 0.25, "axes.spines.top": False, "axes.spines.right": False})
    overview = tables["dataset_overview"]
    fig, ax = plt.subplots(figsize=(9, 4.5))
    ax.barh(overview["dataset"], overview["records"], color="#4c78a8")
    ax.set_xlabel("Records")
    ax.set_title("Final Dataset Sizes")
    ax.invert_yaxis()
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "dataset_sizes.png", dpi=300)
    fig.savefig(FIGURES_DIR / "dataset_sizes.pdf")
    plt.close(fig)

    coverage = tables["attribute_coverage"]
    pivot = coverage.pivot(index="attribute_set", columns="source", values="coverage_percent").fillna(0)
    fig, ax = plt.subplots(figsize=(10, 5.5))
    pivot.plot(kind="barh", ax=ax)
    ax.set_xlabel("Coverage (%)")
    ax.set_title("Attribute Coverage")
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "attribute_coverage.png", dpi=300)
    fig.savefig(FIGURES_DIR / "attribute_coverage.pdf")
    plt.close(fig)

    classification = tables["classification_results"]
    if not classification.empty and "f1_macro" in classification.columns:
        completed = classification[classification.get("status", "completed").eq("completed") if "status" in classification.columns else classification.index == classification.index]
        if "split_name" in completed.columns:
            completed = completed[completed["split_name"].eq("train_test")]
        best = completed.sort_values("f1_macro", ascending=False).groupby("dataset_name", as_index=False).head(6).copy()
        if not best.empty:
            best["label"] = best["dataset_name"] + " | " + best["model_name"] + " | " + best["attribute_set"]
            fig, ax = plt.subplots(figsize=(13, 7))
            ax.barh(best["label"], best["f1_macro"], color="#59a14f")
            ax.set_xlabel("F1 macro")
            ax.set_title("Classification Performance by Dataset, Pipeline, and Attribute Set")
            ax.invert_yaxis()
            fig.tight_layout()
            fig.savefig(FIGURES_DIR / "classification_performance.png", dpi=300)
            fig.savefig(FIGURES_DIR / "classification_performance.pdf")
            plt.close(fig)


def markdown_table(df: pd.DataFrame, max_rows: int | None = None) -> str:
    if max_rows is not None:
        df = df.head(max_rows)
    if df.empty:
        return "No rows."
    columns = list(df.columns)
    lines = ["| " + " | ".join(columns) + " |", "| " + " | ".join("---" for _ in columns) + " |"]
    for _, row in df.iterrows():
        lines.append("| " + " | ".join(str(row[col]) for col in columns) + " |")
    return "\n".join(lines)


def write_report(tables: dict[str, pd.DataFrame], args: argparse.Namespace) -> None:
    overview = tables["dataset_overview"]
    combined = overview[overview["dataset"].eq("final_combined")].iloc[0]
    best = tables.get("best_attribute_results", pd.DataFrame())
    best_cols = [col for col in ["dataset_name", "label_setting", "attribute_set", "model_name", "f1_macro", "f1_micro", "f1_weighted", "accuracy", "subset_accuracy"] if col in best.columns]
    report = f"""# Final Analysis Report

Generated: {datetime.now().isoformat(timespec="seconds")}

Training skipped for this run: `{args.skip_training}`.

## Summary

- Final combined records: {int(combined["records"]):,}
- Records with README content: {int(combined["records_with_readme"]):,}
- Records with SOMEF descriptions: {int(combined["records_with_somef_description"]):,}
- Records with title or abstract: {int(combined["records_with_title_or_abstract"]):,}
- Training datasets: PwC single-only, PwC multi-only, PwC merged, bio.tools single-only, bio.tools multi-only, and bio.tools merged.
- Train/test evaluation: deterministic 80/20 split with random seed {RANDOM_SEED}; the same split is reused across every attribute set and every model within a dataset.
- Cross-validation: `{args.folds}` folds were requested. Fold-level means and standard deviations are written to `final_results/tables/cv_summary.csv` when folds are greater than 1.
- Metrics: macro-F1, micro-F1, weighted-F1, precision/recall, plus accuracy for single-label and subset accuracy/hamming loss for multi-label.
- Model protocol: transformer parameters are never updated. `simple` models use TF-IDF; `bert` models use frozen Hugging Face encoder embeddings plus simple classifiers; `local_llm_*` models use deterministic structured prompts against a local instruction-tuned runtime and require `--enable-local-llm`.

## Dataset Overview

{markdown_table(overview)}

## Best Train/Test Results

{markdown_table(best[best_cols], 24) if best_cols else "No rows."}

## Output Files

- Tables: `final_results/tables/`
- Figures: `final_results/figures/`
- Predictions: `final_results/predictions/predictions.jsonl`
- Splits: `final_results/splits/`
- Report: `final_results/reports/final_analysis_report.md`
- Implementation README: `final_results/README.md`
"""
    (REPORTS_DIR / "final_analysis_report.md").write_text(report, encoding="utf-8")


def write_results_readme(args: argparse.Namespace) -> None:
    text = f"""# Final Results Pipeline README

This folder is generated by `scripts/run_final_results.py`. The script uses only the curated files in `final_datasets/` and writes all result tables, figures, splits, predictions, and logs into `final_results/`.

## Datasets

The runner trains six datasets:

| Dataset | Source | Label setting |
| --- | --- | --- |
| `pwc_single_only` | Papers with Code | exactly one label |
| `pwc_multi_only` | Papers with Code | two or more labels only |
| `pwc_merged` | Papers with Code | single-label and multi-label records together, evaluated as multi-label |
| `biotools_single_only` | bio.tools | exactly one label |
| `biotools_multi_only` | bio.tools | two or more labels only |
| `biotools_merged` | bio.tools | single-label and multi-label records together, evaluated as multi-label |

## Attribute Sets

Each model is trained separately on leakage-audited non-target feature groups: `abstract_only`, `title_only`, `publication_text`, `repository_description`, `readme_only`, `repository_text`, `somef_description_only`, `repository_title_keywords`, `abstract_readme_description`, `abstract_repository_title_keywords`, `all_publication_metadata`, `all_repository_metadata`, and `all_non_target_textual_metadata`.

Target-derived fields are excluded from predictor text: `labels`, `tasks`, `methods`, and `secondary_labels`.

## Implemented Simple Pipelines

1. `tfidf_logistic_regression`
   - Build text from the selected attribute fields.
   - Vectorize with TF-IDF using unigrams/bigrams, `min_df=2`, and up to `{args.max_features}` features.
   - Train a balanced linear logistic-loss classifier with stochastic gradient descent for single-label tasks.
   - Wrap the same classifier in one-vs-rest for multi-label tasks.

2. `tfidf_linear_svm`
   - Use the same TF-IDF representation.
   - Train balanced `LinearSVC` with `max_iter=2500`.
   - Use one-vs-rest for multi-label tasks.

3. `tfidf_random_forest`
   - Use the same TF-IDF representation.
   - Train random forest with `{args.rf_trees}` trees, `balanced_subsample` class weights, and all available CPU cores.
   - Use one-vs-rest for multi-label tasks.

4. `tfidf_xgboost`
   - Use the same TF-IDF representation.
   - Encode class labels for XGBoost and train `XGBClassifier` with histogram trees.
   - Use one-vs-rest for multi-label tasks.
   - If XGBoost is unavailable, the failure is recorded in `classification_results.csv` instead of stopping the run.

5. `tfidf_hard_voting`
   - Run after logistic regression, linear SVM, and random forest have produced predictions.
   - Single-label: choose the majority predicted class.
   - Multi-label: choose labels predicted by a majority of the base models.

## Frozen BERT-Family Pipelines

These pipelines keep model weights frozen. They encode each selected attribute text once with a Hugging Face transformer, save the embeddings under `embeddings/`, and then train the same simple classifiers on top.

| Pipeline | Frozen encoder | Classifier |
| --- | --- | --- |
| `modernbert_embedding_logistic_regression` | `answerdotai/ModernBERT-base` | logistic-loss linear classifier |
| `modernbert_embedding_random_forest` | `answerdotai/ModernBERT-base` | random forest |
| `scibert_embedding_logistic_regression` | `allenai/scibert_scivocab_uncased` | logistic-loss linear classifier |
| `scibert_embedding_random_forest` | `allenai/scibert_scivocab_uncased` | random forest |
| `deberta_v3_embedding_logistic_regression` | `microsoft/deberta-v3-base` | logistic-loss linear classifier |
| `deberta_v3_embedding_random_forest` | `microsoft/deberta-v3-base` | random forest |
| `roberta_embedding_logistic_regression` | `FacebookAI/roberta-base` | logistic-loss linear classifier |
| `roberta_embedding_random_forest` | `FacebookAI/roberta-base` | random forest |

Embedding cache metadata records the Hugging Face model ID, pooling method, tokenizer length, batch size, device, package versions, random seed, and SHA-256 hash of the exact input texts.

## Local LLM Prompt Pipelines

`local_llm_zero_shot`, `local_llm_one_shot`, and `local_llm_few_shot` use the source-controlled prompt in `prompts/local_llm_research_software_classifier.md`, copied into `prompt_templates/` for every run. They require `--enable-local-llm`, an exact `--local-llm-model`, and a `--local-llm-command` that reads the prompt from stdin and returns structured JSON. No data is transmitted to an external commercial API. Responses are cached in `local_llm_cache/`, full prompt/response attempts are saved in `local_llm_conversations/`, and train/test predictions include the local model ID, prompt hash, cache key, conversation path, confidence, abstention flag, evidence snippets, invalid-response counts, parsing attempts, and raw JSON response text.

The default local model placeholder is `{args.local_llm_model}` with temperature `{args.local_llm_temperature}`. Replace it with the exact local model identifier and quantization before running prompt experiments.

## Documented Non-Run Pipelines

The runner writes unavailable or not-yet-configured experiments to `tables/skipped_experiments.csv` when `--include-heavy-skipped` is used. End-to-end transformer weight updates are not part of this protocol.

## Evaluation

The train/test result uses a deterministic 80/20 split with random seed `{RANDOM_SEED}`. Within each dataset, the exact same train/test indices are reused for all attributes and all models; the split files are written to `final_results/splits/`.

Optional cross-validation is controlled by `--folds`. For example, `--folds 3` adds three CV folds and writes fold means and standard deviations to `tables/cv_summary.csv`. The train/test rows remain in `tables/classification_results.csv` with `split_name=train_test`; CV rows use `split_name=cv`.

Metrics include macro-F1, micro-F1, weighted-F1, macro precision, macro recall, and per-class precision/recall/F1/support. Single-label datasets also include accuracy and balanced accuracy. Multi-label datasets also include subset accuracy, hamming loss, and sample-average F1.

## How To Run

Fastest complete simple run, without CV:

```bash
poetry run python scripts/run_final_results.py --models simple --include-heavy-skipped
```

All local non-updating training, including simple TF-IDF and frozen BERT-family embeddings:

```bash
poetry run python scripts/run_final_results.py --models local_all --folds 3 --include-heavy-skipped
```

All configured local experiments, including local instruction-tuned prompting after selecting a model/runtime:

```bash
poetry run python scripts/run_final_results.py --models all --folds 3 --include-heavy-skipped --enable-local-llm --local-llm-model XXX_LOCAL_LLM_MODEL --local-llm-command "YOUR_LOCAL_RUNTIME_COMMAND" --append-results
```

Run one dataset first as a smoke test:

```bash
poetry run python scripts/run_final_results.py --skip-dataset-build --datasets pwc_single_only --attributes abstract_only --models tfidf_logistic_regression,tfidf_random_forest --smoke-test-records 10
```

Run every configured pipeline on 10 records first:

```bash
make training-smoke-all
```

## Main Outputs

| File | Meaning |
| --- | --- |
| `tables/classification_results.csv` | Train/test and optional fold-level metrics for every dataset, attribute set, and model. |
| `tables/cv_summary.csv` | Mean and standard deviation over CV folds, when `--folds` is greater than 1. |
| `tables/per_class_results.csv` | Per-label precision, recall, F1, and support. |
| `tables/skipped_experiments.csv` | Heavy or unavailable experiments documented as not run. |
| `tables/model_metadata.csv` | Model families, encoder IDs, classifiers, and local-runtime flags. |
| `tables/final_analysis_tables.xlsx` | Excel workbook containing the main tables. |
| `figures/*.png` and `figures/*.pdf` | Dataset size, coverage, and performance plots. |
| `predictions/predictions.jsonl` | Test predictions for train/test runs. |
| `reports/final_analysis_report.md` | Human-readable report summary. |
| `reports/run_configuration.json` | Run arguments, package versions, dataset hashes, model registries, and prompt hash. |
| `embeddings/*.npz` and `embeddings/*.json` | Frozen transformer embeddings and their reproducibility metadata. |
| `local_llm_cache/*.json` | Cached local LLM responses keyed by prompt/model/input hash. |
| `local_llm_conversations/*.json` | Full local prompt/response attempts for audit and reuse. |
"""
    (FINAL_RESULTS_DIR / "README.md").write_text(text, encoding="utf-8")


def main() -> None:
    load_dotenv_if_available()
    args = parse_args()
    if args.output_dir is None and args.smoke_test_records:
        args.output_dir = "final_results_smoke"
    if args.output_dir is not None:
        output_dir = Path(args.output_dir)
        if not output_dir.is_absolute():
            output_dir = ROOT / output_dir
        configure_output_paths(output_dir)
    ensure_dirs()
    configure_logging()
    np.random.seed(RANDOM_SEED)
    prompt_template_sha256 = write_prompt_template_snapshot()
    build_final_datasets(args.skip_dataset_build)
    single = load_jsonl("final_single_label.jsonl")
    multi_only = load_jsonl("final_multi_label_only.jsonl")
    combined = load_jsonl("final_combined.jsonl")
    if args.skip_training:
        classification_path = TABLES_DIR / "classification_results.csv"
        if not classification_path.exists():
            raise FileNotFoundError(f"Cannot skip training because {classification_path} does not exist")
        classification = pd.read_csv(classification_path)
        if args.include_heavy_skipped:
            skipped_experiments(all_tasks(single, multi_only, combined), include_heavy=True).to_csv(TABLES_DIR / "skipped_experiments.csv", index=False)
    else:
        classification = run_training(single, multi_only, combined, args)
    tables = save_tables(single, multi_only, combined, classification, args)
    save_figures(tables)
    write_report(tables, args)
    write_results_readme(args)
    config = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "random_seed": RANDOM_SEED,
        "test_size": TEST_SIZE,
        "cross_validation_folds": args.folds,
        "models": selected_models(args.models),
        "datasets": args.datasets,
        "attributes": args.attributes,
        "append_results": args.append_results,
        "skip_existing_results": args.skip_existing_results,
        "output_dir": str(FINAL_RESULTS_DIR.relative_to(ROOT)) if FINAL_RESULTS_DIR.is_relative_to(ROOT) else str(FINAL_RESULTS_DIR),
        "smoke_test_records": args.smoke_test_records,
        "max_tfidf_features": args.max_features,
        "random_forest_trees": args.rf_trees,
        "embedding_batch_size": args.embedding_batch_size,
        "embedding_progress_every": args.embedding_progress_every,
        "embedding_max_length": args.embedding_max_length,
        "embedding_device": args.embedding_device,
        "offline_models_only": args.offline_models_only,
        "trust_remote_code": args.trust_remote_code,
        "enable_local_llm": args.enable_local_llm,
        "local_llm_model": args.local_llm_model,
        "local_llm_command_configured": bool(args.local_llm_command),
        "local_llm_temperature": args.local_llm_temperature,
        "local_llm_max_metadata_chars": args.local_llm_max_metadata_chars,
        "local_llm_few_shot_examples": args.local_llm_few_shot_examples,
        "local_llm_max_retries": args.local_llm_max_retries,
        "local_llm_timeout": args.local_llm_timeout,
        "local_llm_on_cv": args.local_llm_on_cv,
        "local_llm_prompt_template": str(LOCAL_LLM_PROMPT_TEMPLATE.relative_to(ROOT)),
        "local_llm_prompt_template_sha256": prompt_template_sha256,
        "package_versions": package_versions(),
        "input_file_hashes": {
            "final_single_label.jsonl": file_sha256(FINAL_DATASETS_DIR / "final_single_label.jsonl"),
            "final_multi_label_only.jsonl": file_sha256(FINAL_DATASETS_DIR / "final_multi_label_only.jsonl"),
            "final_combined.jsonl": file_sha256(FINAL_DATASETS_DIR / "final_combined.jsonl"),
        },
        "final_datasets_dir": str(FINAL_DATASETS_DIR.relative_to(ROOT)),
        "final_results_dir": str(FINAL_RESULTS_DIR.relative_to(ROOT)),
        "attribute_combinations": ATTRIBUTE_COMBINATIONS,
        "target_fields": TARGET_FIELDS,
        "excluded_leakage_fields": EXCLUDED_LEAKAGE_FIELDS,
        "predictor_field_policy": "Target labels and direct target-derived semantic fields are excluded from predictor text.",
        "frozen_bert_pipelines": FROZEN_BERT_PIPELINES,
        "local_llm_pipelines": LOCAL_LLM_PIPELINES,
        "hardware": {
            "machine": platform.machine(),
            "processor": platform.processor(),
            "python_implementation": platform.python_implementation(),
            "platform": platform.platform(),
        },
    }
    (REPORTS_DIR / "run_configuration.json").write_text(json.dumps(config, indent=2), encoding="utf-8")
    LOGGER.info("Final analysis complete. Results written to %s", FINAL_RESULTS_DIR)


if __name__ == "__main__":
    main()
