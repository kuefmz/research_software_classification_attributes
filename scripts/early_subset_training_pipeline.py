#!/usr/bin/env python3
"""Run preliminary ML baselines on the early enriched subset.

All results produced by this script are preliminary. The input dataset is the
early subset created by ``scripts/early_subset_data_analysis.py`` while
GitHub/SoMEF enrichment is still incomplete.
"""
from __future__ import annotations

import importlib
import json
import logging
import platform
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

try:
    from tqdm import tqdm
except ImportError:  # pragma: no cover
    def tqdm(iterable, **_: object):
        return iterable

sys.path.append(str(Path(__file__).resolve().parent.parent))

from src import config
from src.utils.io_utils import configure_logging, read_jsonl, write_jsonl
from src.utils.text_utils import build_text, clean_list

from sklearn.ensemble import RandomForestClassifier
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    balanced_accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
    hamming_loss,
    precision_score,
    recall_score,
)
from sklearn.model_selection import KFold, StratifiedKFold, train_test_split
from sklearn.multiclass import OneVsRestClassifier
from sklearn.multioutput import MultiOutputClassifier
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import LabelEncoder
from sklearn.preprocessing import MultiLabelBinarizer
from sklearn.svm import LinearSVC


ANALYSIS_STAGE = "early_subset"
RANDOM_SEED = config.RANDOM_SEED
INPUT_DATASET = config.RESULTS_DIR / "early_subset_analysis" / "early_subset_enriched_records.jsonl"
RESULTS_DIR = config.RESULTS_DIR / "early_subset_training"
SPLITS_DIR = config.SPLITS_DIR / "early_subset"
LOG_PATH = RESULTS_DIR / "early_subset_training_pipeline.log"

SUMMARY_CSV = RESULTS_DIR / "summary_results.csv"
PER_CLASS_CSV = RESULTS_DIR / "per_class_results.csv"
SKIPPED_CSV = RESULTS_DIR / "skipped_experiments.csv"
PREDICTIONS_JSONL = RESULTS_DIR / "predictions.jsonl"
RESULTS_XLSX = RESULTS_DIR / "early_subset_training_results.xlsx"
PACKAGE_VERSIONS_JSON = RESULTS_DIR / "package_versions.json"
CONFIG_JSON = RESULTS_DIR / "run_configuration.json"
PROMPTS_DIR = RESULTS_DIR / "prompt_templates"

TEST_SIZE = 0.2
MIN_RECORDS = 40
MIN_LABELS = 2
MIN_CLASS_SUPPORT_FOR_SPLIT = 2
N_FOLDS = 3
MAX_RECORDS_PER_DATASET = 2000
MULTILABEL_MIN_LABEL_SUPPORT = 5
MULTILABEL_MAX_LABELS = 50
RUN_XGBOOST_IF_AVAILABLE = False
RUN_SBERT_IF_AVAILABLE = False
RUN_DOMAIN_EMBEDDINGS = False
RUN_TRANSFORMERS = False
RUN_LLMS = False

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

LOGGER = logging.getLogger("early_subset_training_pipeline")


class EncodedLabelClassifier:
    """Adapter for classifiers such as XGBoost that require integer labels.

    Scikit-learn estimators like LogisticRegression accept string labels
    directly. XGBoost is stricter, so this wrapper encodes labels during fit and
    decodes predictions back to the original class names for evaluation.
    """

    def __init__(self, classifier: Any):
        self.classifier = classifier
        self.encoder = LabelEncoder()

    def fit(self, x: Any, y: list[str]) -> "EncodedLabelClassifier":
        encoded = self.encoder.fit_transform(y)
        self.classifier.fit(x, encoded)
        return self

    def predict(self, x: Any) -> np.ndarray:
        encoded = self.classifier.predict(x)
        return self.encoder.inverse_transform(np.asarray(encoded, dtype=int))


def configure_script_logging() -> None:
    """Configure console and file logging for long experiment runs."""
    configure_logging()
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    root_logger = logging.getLogger()
    if not any(isinstance(handler, logging.FileHandler) and handler.baseFilename == str(LOG_PATH) for handler in root_logger.handlers):
        handler = logging.FileHandler(LOG_PATH, encoding="utf-8")
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s", datefmt="%Y-%m-%d %H:%M:%S"))
        root_logger.addHandler(handler)


def timestamp() -> str:
    """Return a reproducible run timestamp string."""
    return datetime.now().isoformat(timespec="seconds")


def append_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    """Append rows to a JSONL file so predictions are saved immediately."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def save_incremental_tables(summary: list[dict], per_class: list[dict], skipped: list[dict]) -> None:
    """Persist result tables after each experiment to avoid losing progress."""
    pd.DataFrame(summary).to_csv(SUMMARY_CSV, index=False)
    pd.DataFrame(per_class).to_csv(PER_CLASS_CSV, index=False)
    pd.DataFrame(skipped).to_csv(SKIPPED_CSV, index=False)


def package_versions() -> dict[str, str]:
    """Record package versions for reproducibility."""
    packages = ["numpy", "pandas", "sklearn", "scipy", "xgboost", "sentence_transformers", "transformers", "torch"]
    versions = {"python": platform.python_version(), "platform": platform.platform()}
    for package in packages:
        try:
            module = importlib.import_module(package)
            versions[package] = getattr(module, "__version__", "unknown")
        except ImportError:
            versions[package] = "not_installed"
    return versions


def save_run_metadata() -> None:
    """Save constants that define this preliminary training run."""
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    PACKAGE_VERSIONS_JSON.write_text(json.dumps(package_versions(), indent=2, sort_keys=True), encoding="utf-8")
    CONFIG_JSON.write_text(
        json.dumps(
            {
                "analysis_stage": ANALYSIS_STAGE,
                "random_seed": RANDOM_SEED,
                "input_dataset": str(INPUT_DATASET),
                "test_size": TEST_SIZE,
                "min_records": MIN_RECORDS,
                "min_labels": MIN_LABELS,
                "max_records_per_dataset": MAX_RECORDS_PER_DATASET,
                "multilabel_min_label_support": MULTILABEL_MIN_LABEL_SUPPORT,
                "multilabel_max_labels": MULTILABEL_MAX_LABELS,
                "n_folds": N_FOLDS,
                "attribute_combinations": ATTRIBUTE_COMBINATIONS,
                "run_xgboost_if_available": RUN_XGBOOST_IF_AVAILABLE,
                "run_sbert_if_available": RUN_SBERT_IF_AVAILABLE,
                "run_domain_embeddings": RUN_DOMAIN_EMBEDDINGS,
                "run_transformers": RUN_TRANSFORMERS,
                "run_llms": RUN_LLMS,
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )


def save_prompt_templates() -> None:
    """Save deterministic LLM prompt templates for later experiments."""
    PROMPTS_DIR.mkdir(parents=True, exist_ok=True)
    zero_shot = """You are classifying research software metadata.
Available labels:
{labels}

Metadata:
{metadata}

Return exactly one JSON object with a key "labels" containing the predicted label list.
"""
    few_shot = """You are classifying research software metadata.
Use the examples to infer the label space and output style.

Examples:
{examples}

Target metadata:
{metadata}

Return exactly one JSON object with a key "labels" containing the predicted label list.
"""
    (PROMPTS_DIR / "zero_shot_template.txt").write_text(zero_shot, encoding="utf-8")
    (PROMPTS_DIR / "few_shot_template.txt").write_text(few_shot, encoding="utf-8")


def load_records() -> list[dict[str, Any]]:
    """Load the enriched early subset generated by the analysis script."""
    if not INPUT_DATASET.exists():
        raise FileNotFoundError(f"Run scripts/early_subset_data_analysis.py first: {INPUT_DATASET}")
    records = list(read_jsonl(INPUT_DATASET))
    LOGGER.info("Loaded early subset records: %s", f"{len(records):,}")
    return records


def make_dataset(records: list[dict[str, Any]], source: str, label_setting: str) -> list[dict[str, Any]]:
    """Create one source/label-setting dataset from enriched records."""
    subset = [record for record in records if record.get("source") == source]
    output = []
    for record in subset:
        labels = clean_list(record.get("labels"))
        if label_setting == "single" and len(labels) == 1:
            row = dict(record)
            row["target"] = labels[0]
            output.append(row)
        elif label_setting == "multi" and labels:
            row = dict(record)
            row["target"] = labels
            output.append(row)
    if label_setting == "multi":
        support = Counter(label for record in output for label in record["target"])
        kept_labels = {
            label
            for label, count in support.most_common(MULTILABEL_MAX_LABELS)
            if count >= MULTILABEL_MIN_LABEL_SUPPORT
        }
        filtered = []
        for record in output:
            labels = [label for label in record["target"] if label in kept_labels]
            if labels:
                row = dict(record)
                row["target"] = labels
                row["labels"] = labels
                filtered.append(row)
        output = filtered
    if MAX_RECORDS_PER_DATASET and len(output) > MAX_RECORDS_PER_DATASET:
        rng = np.random.default_rng(RANDOM_SEED)
        selected = sorted(rng.choice(len(output), size=MAX_RECORDS_PER_DATASET, replace=False).tolist())
        output = [output[index] for index in selected]
    return output


def dataset_name(source: str, label_setting: str) -> str:
    """Return stable dataset identifier."""
    return f"{source.replace('.', '').replace('_with_code', '')}_{label_setting}_label"


def skip(skipped: list[dict], reason: str, **metadata: Any) -> None:
    """Record a skipped experiment with enough context to audit it later."""
    row = {"analysis_stage": ANALYSIS_STAGE, "timestamp": timestamp(), "reason": reason, **metadata}
    skipped.append(row)
    LOGGER.warning("Skipping: %s | %s", reason, metadata)


def valid_label_summary(records: list[dict], label_setting: str) -> tuple[int, Counter]:
    """Return number of labels and support counts."""
    if label_setting == "single":
        counter = Counter(record["target"] for record in records)
    else:
        counter = Counter(label for record in records for label in record["target"])
    return len(counter), counter


def create_or_load_split(records: list[dict], dataset_id: str, label_setting: str, skipped: list[dict]) -> dict[str, list[int]]:
    """Create deterministic train/test indices and reuse them across models."""
    SPLITS_DIR.mkdir(parents=True, exist_ok=True)
    split_path = SPLITS_DIR / f"{dataset_id}_split.json"
    if split_path.exists():
        split = json.loads(split_path.read_text(encoding="utf-8"))
        all_indices = split.get("train_indices", []) + split.get("test_indices", [])
        if all_indices and max(all_indices) < len(records) and split.get("num_records") == len(records):
            return split
        LOGGER.warning("Ignoring stale split file with indices outside current dataset: %s", split_path)

    indices = np.arange(len(records))
    if label_setting == "single":
        y = np.array([record["target"] for record in records])
        counts = Counter(y)
        stratify = y if len(counts) >= MIN_LABELS and min(counts.values()) >= MIN_CLASS_SUPPORT_FOR_SPLIT else None
        if stratify is None:
            skip(skipped, "single-label stratified split unavailable; using deterministic random split", dataset_name=dataset_id)
        train_idx, test_idx = train_test_split(indices, test_size=TEST_SIZE, random_state=RANDOM_SEED, stratify=stratify)
    else:
        train_idx, test_idx = train_test_split(indices, test_size=TEST_SIZE, random_state=RANDOM_SEED)
        skip(skipped, "iterative multi-label stratification not available in this early script; using deterministic random split", dataset_name=dataset_id)
    split = {
        "split_id": f"{dataset_id}_seed_{RANDOM_SEED}",
        "num_records": len(records),
        "train_indices": train_idx.tolist(),
        "test_indices": test_idx.tolist(),
    }
    split_path.write_text(json.dumps(split, indent=2, sort_keys=True), encoding="utf-8")
    return split


def create_or_load_folds(records: list[dict], dataset_id: str, label_setting: str, skipped: list[dict]) -> list[dict[str, list[int]]]:
    """Create deterministic folds where enough data exists."""
    folds_path = SPLITS_DIR / f"{dataset_id}_folds.json"
    if folds_path.exists():
        folds = json.loads(folds_path.read_text(encoding="utf-8"))
        all_indices = [index for fold in folds for index in fold.get("train_indices", []) + fold.get("test_indices", [])]
        if all_indices and max(all_indices) < len(records) and all(fold.get("num_records") == len(records) for fold in folds):
            return folds
        LOGGER.warning("Ignoring stale folds file with indices outside current dataset: %s", folds_path)
    if len(records) < N_FOLDS * 10:
        skip(skipped, "too few records for k-fold cross-validation", dataset_name=dataset_id, num_records=len(records))
        return []
    indices = np.arange(len(records))
    folds = []
    if label_setting == "single":
        y = np.array([record["target"] for record in records])
        counts = Counter(y)
        if min(counts.values()) < N_FOLDS:
            skip(skipped, "too few samples in at least one class for stratified folds", dataset_name=dataset_id)
            return []
        splitter = StratifiedKFold(n_splits=N_FOLDS, shuffle=True, random_state=RANDOM_SEED)
        iterator = splitter.split(indices, y)
    else:
        splitter = KFold(n_splits=N_FOLDS, shuffle=True, random_state=RANDOM_SEED)
        iterator = splitter.split(indices)
    for fold_id, (train_idx, test_idx) in enumerate(iterator):
        folds.append({"fold_id": fold_id, "num_records": len(records), "train_indices": train_idx.tolist(), "test_indices": test_idx.tolist()})
    folds_path.write_text(json.dumps(folds, indent=2, sort_keys=True), encoding="utf-8")
    return folds


def build_texts(records: list[dict], attribute_name: str) -> list[str]:
    """Create model input text for one attribute combination."""
    fields = ATTRIBUTE_COMBINATIONS[attribute_name]
    return [build_text(record, fields) for record in records]


def model_specs(label_setting: str) -> list[dict[str, Any]]:
    """Return model specifications for currently enabled early baselines."""
    specs: list[dict[str, Any]] = [
        {
            "model_name": "tfidf_logistic_regression",
            "vectorizer_or_embedding": "tfidf",
            "classifier": "LogisticRegression",
            "factory": lambda: LogisticRegression(max_iter=2000, class_weight="balanced", random_state=RANDOM_SEED),
        },
        {
            "model_name": "tfidf_linear_svm",
            "vectorizer_or_embedding": "tfidf",
            "classifier": "LinearSVC",
            "factory": lambda: LinearSVC(class_weight="balanced", random_state=RANDOM_SEED),
        },
        {
            "model_name": "tfidf_random_forest",
            "vectorizer_or_embedding": "tfidf",
            "classifier": "RandomForestClassifier",
            "factory": lambda: RandomForestClassifier(n_estimators=200, random_state=RANDOM_SEED, n_jobs=-1, class_weight="balanced_subsample"),
        },
    ]
    if RUN_XGBOOST_IF_AVAILABLE:
        try:
            from xgboost import XGBClassifier

            specs.append(
                {
                    "model_name": "tfidf_xgboost",
                    "vectorizer_or_embedding": "tfidf",
                    "classifier": "XGBClassifier",
                    "factory": lambda: XGBClassifier(
                        n_estimators=200,
                        max_depth=6,
                        learning_rate=0.1,
                        subsample=0.9,
                        colsample_bytree=0.9,
                        random_state=RANDOM_SEED,
                        eval_metric="logloss",
                        n_jobs=1,
                    ),
                }
            )
        except ImportError:
            pass
    return specs


def wrap_classifier(base_classifier: Any, label_setting: str, classifier_name: str) -> Any:
    """Wrap estimators for multi-label targets where needed."""
    if label_setting == "single" and classifier_name == "XGBClassifier":
        return EncodedLabelClassifier(base_classifier)
    if label_setting == "multi":
        if classifier_name in {"LogisticRegression", "LinearSVC", "XGBClassifier"}:
            return OneVsRestClassifier(base_classifier)
        if classifier_name == "RandomForestClassifier":
            return MultiOutputClassifier(base_classifier)
    return base_classifier


def make_pipeline(spec: dict[str, Any], label_setting: str) -> Pipeline:
    """Create a TF-IDF classification pipeline."""
    classifier = wrap_classifier(spec["factory"](), label_setting, spec["classifier"])
    return Pipeline(
        [
            ("tfidf", TfidfVectorizer(max_features=50000, ngram_range=(1, 2), min_df=2)),
            ("classifier", classifier),
        ]
    )


def single_metrics(y_true: list[str], y_pred: list[str]) -> dict[str, float]:
    """Compute single-label metrics used in the paper tables."""
    return {
        "accuracy": accuracy_score(y_true, y_pred),
        "balanced_accuracy": balanced_accuracy_score(y_true, y_pred),
        "precision_micro": precision_score(y_true, y_pred, average="micro", zero_division=0),
        "precision_macro": precision_score(y_true, y_pred, average="macro", zero_division=0),
        "precision_weighted": precision_score(y_true, y_pred, average="weighted", zero_division=0),
        "recall_micro": recall_score(y_true, y_pred, average="micro", zero_division=0),
        "recall_macro": recall_score(y_true, y_pred, average="macro", zero_division=0),
        "recall_weighted": recall_score(y_true, y_pred, average="weighted", zero_division=0),
        "f1_micro": f1_score(y_true, y_pred, average="micro", zero_division=0),
        "f1_macro": f1_score(y_true, y_pred, average="macro", zero_division=0),
        "f1_weighted": f1_score(y_true, y_pred, average="weighted", zero_division=0),
    }


def multilabel_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> dict[str, float]:
    """Compute multi-label metrics used in the paper tables."""
    return {
        "subset_accuracy": accuracy_score(y_true, y_pred),
        "hamming_loss": hamming_loss(y_true, y_pred),
        "precision_micro": precision_score(y_true, y_pred, average="micro", zero_division=0),
        "precision_macro": precision_score(y_true, y_pred, average="macro", zero_division=0),
        "precision_weighted": precision_score(y_true, y_pred, average="weighted", zero_division=0),
        "precision_samples": precision_score(y_true, y_pred, average="samples", zero_division=0),
        "recall_micro": recall_score(y_true, y_pred, average="micro", zero_division=0),
        "recall_macro": recall_score(y_true, y_pred, average="macro", zero_division=0),
        "recall_weighted": recall_score(y_true, y_pred, average="weighted", zero_division=0),
        "recall_samples": recall_score(y_true, y_pred, average="samples", zero_division=0),
        "f1_micro": f1_score(y_true, y_pred, average="micro", zero_division=0),
        "f1_macro": f1_score(y_true, y_pred, average="macro", zero_division=0),
        "f1_weighted": f1_score(y_true, y_pred, average="weighted", zero_division=0),
        "f1_samples": f1_score(y_true, y_pred, average="samples", zero_division=0),
    }


def per_class_rows(y_true: Any, y_pred: Any, labels: list[str], base_metadata: dict[str, Any], label_setting: str) -> list[dict[str, Any]]:
    """Create per-class precision/recall/F1 rows."""
    report = classification_report(y_true, y_pred, target_names=labels if label_setting == "multi" else None, output_dict=True, zero_division=0)
    rows = []
    for label in labels:
        metrics = report.get(label)
        if not isinstance(metrics, dict):
            continue
        rows.append(
            {
                **base_metadata,
                "class_label": label,
                "precision": metrics.get("precision"),
                "recall": metrics.get("recall"),
                "f1": metrics.get("f1-score"),
                "support": metrics.get("support"),
            }
        )
    return rows


def evaluate_split(
    records: list[dict],
    train_indices: list[int],
    test_indices: list[int],
    attribute_name: str,
    spec: dict[str, Any],
    dataset_metadata: dict[str, Any],
    label_setting: str,
    fold_id: str | int | None,
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    """Train and evaluate one model/attribute/split."""
    texts = build_texts(records, attribute_name)
    if not any(texts[index] for index in train_indices):
        raise ValueError("No non-empty training text for attribute combination")
    pipeline = make_pipeline(spec, label_setting)
    x_train = [texts[index] for index in train_indices]
    x_test = [texts[index] for index in test_indices]

    if label_setting == "single":
        y = [record["target"] for record in records]
        y_train = [y[index] for index in train_indices]
        y_test = [y[index] for index in test_indices]
        pipeline.fit(x_train, y_train)
        y_pred = pipeline.predict(x_test)
        metrics = single_metrics(y_test, y_pred)
        labels = sorted(set(y_test) | set(y_pred))
        per_class = per_class_rows(y_test, y_pred, labels, dataset_metadata, label_setting)
        prediction_rows = [
            {
                **dataset_metadata,
                "record_id": records[index].get("item_id"),
                "true_label": y_test[pos],
                "predicted_label": str(y_pred[pos]),
            }
            for pos, index in enumerate(test_indices)
        ]
    else:
        mlb = MultiLabelBinarizer()
        y_all = mlb.fit_transform([record["target"] for record in records])
        y_train = y_all[train_indices]
        y_test = y_all[test_indices]
        pipeline.fit(x_train, y_train)
        y_pred = pipeline.predict(x_test)
        metrics = multilabel_metrics(y_test, y_pred)
        labels = list(mlb.classes_)
        per_class = per_class_rows(y_test, y_pred, labels, dataset_metadata, label_setting)
        prediction_rows = [
            {
                **dataset_metadata,
                "record_id": records[index].get("item_id"),
                "true_label": list(mlb.inverse_transform(y_test[[pos]])[0]),
                "predicted_label": list(mlb.inverse_transform(y_pred[[pos]])[0]),
            }
            for pos, index in enumerate(test_indices)
        ]

    summary = {
        **dataset_metadata,
        "fold_id": fold_id,
        **metrics,
    }
    return summary, per_class, prediction_rows


def save_confusion_matrix(records: list[dict], split: dict, attribute_name: str, spec: dict, dataset_metadata: dict) -> None:
    """Save a confusion matrix for single-label train/test experiments."""
    if dataset_metadata["label_setting"] != "single":
        return
    texts = build_texts(records, attribute_name)
    y = [record["target"] for record in records]
    pipeline = make_pipeline(spec, "single")
    pipeline.fit([texts[i] for i in split["train_indices"]], [y[i] for i in split["train_indices"]])
    y_true = [y[i] for i in split["test_indices"]]
    y_pred = pipeline.predict([texts[i] for i in split["test_indices"]])
    labels = sorted(set(y_true) | set(y_pred))
    matrix = confusion_matrix(y_true, y_pred, labels=labels)
    out_dir = RESULTS_DIR / "confusion_matrices"
    out_dir.mkdir(parents=True, exist_ok=True)
    matrix_path = out_dir / f"{dataset_metadata['dataset_name']}__{attribute_name}__{spec['model_name']}.csv"
    pd.DataFrame(matrix, index=labels, columns=labels).to_csv(matrix_path)


def dataset_overview_rows(datasets: dict[str, list[dict]]) -> list[dict]:
    """Summarize constructed datasets."""
    rows = []
    for name, records in datasets.items():
        label_setting = "multi" if name.endswith("multi_label") else "single"
        num_labels, support = valid_label_summary(records, label_setting)
        rows.append(
            {
                "analysis_stage": ANALYSIS_STAGE,
                "dataset_name": name,
                "num_records": len(records),
                "num_labels": num_labels,
                "min_label_support": min(support.values()) if support else 0,
                "max_label_support": max(support.values()) if support else 0,
            }
        )
    return rows


def attribute_coverage_rows(datasets: dict[str, list[dict]]) -> list[dict]:
    """Summarize text coverage by dataset and attribute combination."""
    rows = []
    for dataset_id, records in datasets.items():
        for attribute_name in ATTRIBUTE_COMBINATIONS:
            texts = build_texts(records, attribute_name)
            rows.append(
                {
                    "analysis_stage": ANALYSIS_STAGE,
                    "dataset_name": dataset_id,
                    "attribute_combination": attribute_name,
                    "records_with_text": sum(bool(text) for text in texts),
                    "num_records": len(records),
                    "coverage_percent": sum(bool(text) for text in texts) / len(records) * 100 if records else 0,
                }
            )
    return rows


def run_placeholder_sections(skipped: list[dict]) -> list[dict]:
    """Document intentionally disabled heavy experiment sections."""
    metadata = []
    for model_family, enabled in [
        ("sbert_embeddings", RUN_SBERT_IF_AVAILABLE),
        ("scibert_specter_domain_embeddings", RUN_DOMAIN_EMBEDDINGS),
        ("transformer_weight_updates", RUN_TRANSFORMERS),
        ("llm_zero_few_shot", RUN_LLMS),
    ]:
        row = {
            "analysis_stage": ANALYSIS_STAGE,
            "timestamp": timestamp(),
            "model_family": model_family,
            "enabled": enabled,
            "note": "Placeholder prepared. Disabled by default for early subset script to avoid heavy downloads/training.",
        }
        metadata.append(row)
        if not enabled:
            skipped.append({"analysis_stage": ANALYSIS_STAGE, "timestamp": timestamp(), "reason": "heavy optional section disabled", "model_family": model_family})
    return metadata


def write_excel(summary: list[dict], per_class: list[dict], skipped: list[dict], dataset_overview: list[dict], attribute_coverage: list[dict], model_metadata: list[dict]) -> None:
    """Write the requested multi-sheet training workbook."""
    try:
        with pd.ExcelWriter(RESULTS_XLSX) as writer:
            pd.DataFrame(summary).to_excel(writer, sheet_name="summary_results", index=False)
            pd.DataFrame(per_class).to_excel(writer, sheet_name="per_class_results", index=False)
            pd.DataFrame(skipped).to_excel(writer, sheet_name="skipped_experiments", index=False)
            pd.DataFrame(dataset_overview).to_excel(writer, sheet_name="dataset_overview", index=False)
            pd.DataFrame(attribute_coverage).to_excel(writer, sheet_name="attribute_coverage", index=False)
            pd.DataFrame(model_metadata).to_excel(writer, sheet_name="model_metadata", index=False)
    except Exception as exc:
        LOGGER.warning("Could not write Excel workbook %s: %s", RESULTS_XLSX, exc)


def main() -> None:
    configure_script_logging()
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    SPLITS_DIR.mkdir(parents=True, exist_ok=True)
    save_run_metadata()
    save_prompt_templates()
    if PREDICTIONS_JSONL.exists():
        PREDICTIONS_JSONL.unlink()

    records = load_records()
    datasets = {
        dataset_name("papers_with_code", "single"): make_dataset(records, "papers_with_code", "single"),
        dataset_name("papers_with_code", "multi"): make_dataset(records, "papers_with_code", "multi"),
        dataset_name("bio.tools", "single"): make_dataset(records, "bio.tools", "single"),
        dataset_name("bio.tools", "multi"): make_dataset(records, "bio.tools", "multi"),
    }

    summary_results: list[dict[str, Any]] = []
    per_class_results: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    dataset_overview = dataset_overview_rows(datasets)
    attribute_coverage = attribute_coverage_rows(datasets)
    model_metadata = run_placeholder_sections(skipped)
    if not RUN_XGBOOST_IF_AVAILABLE:
        skipped.append(
            {
                "analysis_stage": ANALYSIS_STAGE,
                "timestamp": timestamp(),
                "reason": "xgboost disabled by RUN_XGBOOST_IF_AVAILABLE for fast early subset run",
                "model_name": "tfidf_xgboost",
            }
        )

    for dataset_id, dataset_records in datasets.items():
        label_setting = "multi" if dataset_id.endswith("multi_label") else "single"
        source_dataset = "bio.tools" if dataset_id.startswith("biotools") else "papers_with_code"
        num_labels, label_support = valid_label_summary(dataset_records, label_setting)
        if len(dataset_records) < MIN_RECORDS or num_labels < MIN_LABELS:
            skip(skipped, "dataset too small or too few labels", dataset_name=dataset_id, num_records=len(dataset_records), num_labels=num_labels)
            continue

        split = create_or_load_split(dataset_records, dataset_id, label_setting, skipped)
        folds = create_or_load_folds(dataset_records, dataset_id, label_setting, skipped)
        specs = model_specs(label_setting)
        if RUN_XGBOOST_IF_AVAILABLE and not any(spec["classifier"] == "XGBClassifier" for spec in specs):
            skip(skipped, "xgboost not installed", dataset_name=dataset_id, model_name="tfidf_xgboost")

        for attribute_name in ATTRIBUTE_COMBINATIONS:
            texts = build_texts(dataset_records, attribute_name)
            if sum(bool(text) for text in texts) < MIN_RECORDS:
                skip(skipped, "too few records with non-empty text", dataset_name=dataset_id, attribute_combination=attribute_name)
                continue
            for spec in tqdm(specs, desc=f"{dataset_id} {attribute_name}"):
                base_metadata = {
                    "analysis_stage": ANALYSIS_STAGE,
                    "timestamp": timestamp(),
                    "source_dataset": source_dataset,
                    "label_setting": label_setting,
                    "dataset_name": dataset_id,
                    "num_records": len(dataset_records),
                    "num_train": len(split["train_indices"]),
                    "num_test": len(split["test_indices"]),
                    "num_labels": num_labels,
                    "attribute_combination": attribute_name,
                    "model_name": spec["model_name"],
                    "vectorizer_or_embedding": spec["vectorizer_or_embedding"],
                    "classifier": spec["classifier"],
                    "random_seed": RANDOM_SEED,
                    "split_id": split["split_id"],
                }
                try:
                    summary, per_class, predictions = evaluate_split(
                        dataset_records,
                        split["train_indices"],
                        split["test_indices"],
                        attribute_name,
                        spec,
                        base_metadata,
                        label_setting,
                        fold_id="train_test",
                    )
                    summary_results.append(summary)
                    per_class_results.extend(per_class)
                    append_jsonl(PREDICTIONS_JSONL, predictions)
                    save_confusion_matrix(dataset_records, split, attribute_name, spec, base_metadata)

                    fold_metrics = []
                    for fold in folds:
                        fold_metadata = {**base_metadata, "split_id": f"{dataset_id}_cv_seed_{RANDOM_SEED}"}
                        fold_summary, fold_per_class, _ = evaluate_split(
                            dataset_records,
                            fold["train_indices"],
                            fold["test_indices"],
                            attribute_name,
                            spec,
                            fold_metadata,
                            label_setting,
                            fold_id=fold["fold_id"],
                        )
                        summary_results.append(fold_summary)
                        per_class_results.extend(fold_per_class)
                        fold_metrics.append(fold_summary)
                    if fold_metrics:
                        metric_keys = [key for key, value in fold_metrics[0].items() if isinstance(value, (int, float)) and key not in {"num_records", "num_train", "num_test", "num_labels", "random_seed"}]
                        aggregate = {**base_metadata, "fold_id": "cv_mean_std"}
                        for key in metric_keys:
                            values = [row[key] for row in fold_metrics if key in row]
                            aggregate[f"{key}_mean"] = float(np.mean(values))
                            aggregate[f"{key}_std"] = float(np.std(values))
                        summary_results.append(aggregate)
                except Exception as exc:
                    skip(skipped, f"experiment failed: {exc}", **base_metadata)
                save_incremental_tables(summary_results, per_class_results, skipped)

    save_incremental_tables(summary_results, per_class_results, skipped)
    pd.DataFrame(dataset_overview).to_csv(RESULTS_DIR / "dataset_overview.csv", index=False)
    pd.DataFrame(attribute_coverage).to_csv(RESULTS_DIR / "attribute_coverage.csv", index=False)
    pd.DataFrame(model_metadata).to_csv(RESULTS_DIR / "model_metadata.csv", index=False)
    write_excel(summary_results, per_class_results, skipped, dataset_overview, attribute_coverage, model_metadata)
    LOGGER.info("Early subset training complete. Results written to %s", RESULTS_DIR)


if __name__ == "__main__":
    main()
