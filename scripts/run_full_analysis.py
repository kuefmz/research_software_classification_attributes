#!/usr/bin/env python3
"""Run the full local-only reproducible analysis.

This script deliberately consumes only files already present in the repository.
It does not rerun SoMEF, fetch Papers with Code or bio.tools data, query GitHub,
call OpenAlex, or use remote embedding/model APIs.
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

sys.path.append(str(Path(__file__).resolve().parent.parent))

from src import config
from src.utils.io_utils import configure_logging, read_jsonl, write_json
from src.utils.text_utils import build_text, clean_list, flatten_for_text


ROOT = Path(__file__).resolve().parent.parent
PROCESSED_DIR = config.DATA_DIR / "processed"
TABLES_DIR = config.RESULTS_DIR / "tables"
FIGURES_DIR = config.RESULTS_DIR / "figures"
REPORTS_DIR = config.RESULTS_DIR / "reports"
LOGS_DIR = config.RESULTS_DIR / "logs"
RUN_LOG = LOGS_DIR / "full_analysis.log"
RUN_CONFIG = REPORTS_DIR / "analysis_run_config.json"
SUMMARY_REPORT = REPORTS_DIR / "analysis_summary.md"
TRAINING_SCRIPT = ROOT / "scripts" / "full_training_pipeline.py"
FINAL_DATASET_DIR = config.DATA_DIR / "final_edam_top_level"

DATASET_INPUTS = {
    "pwc_single_label": FINAL_DATASET_DIR / "pwc_single_label.jsonl",
    "pwc_multi_label": FINAL_DATASET_DIR / "pwc_multi_label.jsonl",
    "biotools_single_label": FINAL_DATASET_DIR / "biotools_single_label.jsonl",
    "biotools_multi_label": FINAL_DATASET_DIR / "biotools_multi_label.jsonl",
    "combined_all": FINAL_DATASET_DIR / "combined_all.jsonl",
    "pwc_single_label_with_somef": FINAL_DATASET_DIR / "pwc_single_label_with_somef.jsonl",
    "pwc_multi_label_with_somef": FINAL_DATASET_DIR / "pwc_multi_label_with_somef.jsonl",
    "biotools_single_label_with_somef": FINAL_DATASET_DIR / "biotools_single_label_with_somef.jsonl",
    "biotools_multi_label_with_somef": FINAL_DATASET_DIR / "biotools_multi_label_with_somef.jsonl",
    "combined_all_with_somef": FINAL_DATASET_DIR / "combined_all_with_somef.jsonl",
}

RAW_AND_INTERIM_INPUTS = {
    "papers_with_code_merged": config.PWC_MERGED_JSONL,
    "bio_tools_flat": config.BIOTOOLS_FLAT_CSV,
    "bio_tools_raw": config.BIOTOOLS_RAW_JSONL,
    "pwc_aligned": config.PWC_ALIGNED_JSONL,
    "biotools_aligned": config.BIOTOOLS_ALIGNED_JSONL,
    "somef_artifacts": config.REPOSITORY_ARTIFACTS_DIR,
}

ATTRIBUTE_FIELDS = {
    "paper_title": ["paper_title"],
    "paper_abstract": ["paper_abstract"],
    "software_name": ["software_name"],
    "software_description": ["software_description"],
    "repository_title": ["repository_title"],
    "repository_description": ["repository_description"],
    "github_keywords": ["repository_keywords", "somef_keywords"],
    "readme_content": ["readme_content"],
    "somef_description": ["somef_description"],
    "publication_metadata": ["paper_title", "paper_abstract", "publication_url"],
    "repository_metadata": ["repository_title", "repository_description", "repository_keywords", "readme_content", "somef_description"],
    "all_non_target_textual_metadata": config.ATTRIBUTE_COMBINATIONS["all_non_target_textual_metadata"],
}

LOGGER = logging.getLogger("full_local_analysis")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--skip-training",
        action="store_true",
        help="Do not rerun the local TF-IDF training script; summarize existing saved results instead.",
    )
    return parser.parse_args()


def configure_script_logging() -> None:
    configure_logging()
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    root_logger = logging.getLogger()
    if not any(isinstance(handler, logging.FileHandler) and handler.baseFilename == str(RUN_LOG) for handler in root_logger.handlers):
        handler = logging.FileHandler(RUN_LOG, encoding="utf-8")
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s", datefmt="%Y-%m-%d %H:%M:%S"))
        root_logger.addHandler(handler)


def require_local_inputs() -> None:
    missing = [f"{name}: {path}" for name, path in {**RAW_AND_INTERIM_INPUTS, **DATASET_INPUTS}.items() if not path.exists()]
    if missing:
        joined = "\n".join(f"- {item}" for item in missing)
        raise FileNotFoundError(f"Required local input files are missing:\n{joined}")


def ensure_output_dirs() -> None:
    for path in [PROCESSED_DIR, TABLES_DIR, FIGURES_DIR, REPORTS_DIR, LOGS_DIR]:
        path.mkdir(parents=True, exist_ok=True)


def load_dataset(path: Path) -> list[dict[str, Any]]:
    return list(read_jsonl(path))


def write_processed_copy(name: str, source_path: Path) -> None:
    target_jsonl = PROCESSED_DIR / f"{name}.jsonl"
    target_csv = PROCESSED_DIR / f"{name}.csv"
    shutil.copyfile(source_path, target_jsonl)
    records = load_dataset(source_path)
    pd.DataFrame(records).to_csv(target_csv, index=False)


def save_processed_datasets() -> dict[str, list[dict[str, Any]]]:
    datasets: dict[str, list[dict[str, Any]]] = {}
    for name, path in DATASET_INPUTS.items():
        LOGGER.info("Writing processed dataset copy for %s", name)
        write_processed_copy(name, path)
        datasets[name] = load_dataset(path)
    return datasets


def has_value(record: dict[str, Any], fields: list[str]) -> bool:
    return any(bool(build_text(record, [field])) for field in fields)


def source_name(record: dict[str, Any]) -> str:
    source = record.get("source")
    if source == "bio.tools":
        return "bio.tools"
    return str(source or "unknown")


def dataset_overview_table(datasets: dict[str, list[dict[str, Any]]]) -> pd.DataFrame:
    rows = []
    for dataset_name, records in datasets.items():
        label_counts = [len(clean_list(record.get("labels"))) for record in records]
        rows.append(
            {
                "dataset": dataset_name,
                "records": len(records),
                "sources": ", ".join(sorted({source_name(record) for record in records})),
                "records_with_github_links": sum(bool(record.get("repository_url")) for record in records),
                "records_with_readme": sum(has_value(record, ["readme_content"]) for record in records),
                "records_with_somef_description": sum(has_value(record, ["somef_description"]) for record in records),
                "records_with_github_keywords": sum(has_value(record, ["repository_keywords", "somef_keywords"]) for record in records),
                "records_with_title_or_abstract": sum(has_value(record, ["paper_title", "paper_abstract"]) for record in records),
                "single_label_records": sum(count == 1 for count in label_counts),
                "multi_label_records": sum(count > 1 for count in label_counts),
                "unique_labels": len({label for record in records for label in clean_list(record.get("labels"))}),
            }
        )
    return pd.DataFrame(rows)


def coverage_table(records: list[dict[str, Any]], dataset_label: str) -> pd.DataFrame:
    rows = []
    for source in sorted({source_name(record) for record in records}):
        source_records = [record for record in records if source_name(record) == source]
        total = len(source_records)
        for attribute, fields in ATTRIBUTE_FIELDS.items():
            count = sum(has_value(record, fields) for record in source_records)
            rows.append(
                {
                    "dataset": dataset_label,
                    "source": source,
                    "attribute": attribute,
                    "records_with_attribute": count,
                    "records": total,
                    "coverage_percent": count / total * 100 if total else 0.0,
                }
            )
    return pd.DataFrame(rows)


def missing_value_table(records: list[dict[str, Any]]) -> pd.DataFrame:
    rows = []
    total = len(records)
    fields = sorted({field for fields in ATTRIBUTE_FIELDS.values() for field in fields} | {"repository_url", "labels", "tasks", "methods", "secondary_labels"})
    for field in fields:
        count = sum(bool(clean_list(record.get(field)) if isinstance(record.get(field), list) else flatten_for_text(record.get(field))) for record in records)
        rows.append({"field": field, "non_missing": count, "missing": total - count, "missing_percent": (total - count) / total * 100 if total else 0.0})
    return pd.DataFrame(rows)


def label_distribution_table(records: list[dict[str, Any]]) -> pd.DataFrame:
    rows = []
    for source in sorted({source_name(record) for record in records}):
        source_records = [record for record in records if source_name(record) == source]
        total_assignments = sum(len(clean_list(record.get("labels"))) for record in source_records)
        counts: dict[str, int] = {}
        for record in source_records:
            for label in clean_list(record.get("labels")):
                counts[label] = counts.get(label, 0) + 1
        for label, count in sorted(counts.items(), key=lambda item: (-item[1], item[0].casefold())):
            rows.append(
                {
                    "source": source,
                    "label": label,
                    "support": count,
                    "percent_of_label_assignments": count / total_assignments * 100 if total_assignments else 0.0,
                }
            )
    return pd.DataFrame(rows)


def long_tail_table(label_distribution: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for source, group in label_distribution.groupby("source"):
        support = group["support"]
        rows.append(
            {
                "source": source,
                "num_labels": int(len(group)),
                "labels_with_support_1": int((support == 1).sum()),
                "labels_with_support_lt_5": int((support < 5).sum()),
                "median_support": float(support.median()) if len(support) else 0.0,
                "max_support": int(support.max()) if len(support) else 0,
            }
        )
    return pd.DataFrame(rows)


def classification_tables() -> tuple[pd.DataFrame, pd.DataFrame]:
    summary_path = config.RESULTS_DIR / "training" / "summary_results.csv"
    if not summary_path.exists():
        LOGGER.warning("Classification summary is missing: %s", summary_path)
        return pd.DataFrame(), pd.DataFrame()
    summary = pd.read_csv(summary_path)
    summary.to_csv(TABLES_DIR / "classification_results.csv", index=False)
    metric = "f1_macro"
    metric_column = metric if metric in summary.columns else "f1_macro_mean"
    best = summary[summary["fold_id"].eq("train_test")].copy() if "fold_id" in summary.columns else summary.copy()
    if metric_column in best.columns and not best.empty:
        best = best.sort_values(metric_column, ascending=False).groupby(["source_dataset", "label_setting"], as_index=False).head(10)
    best.to_csv(TABLES_DIR / "best_attribute_model_combinations.csv", index=False)
    return summary, best


def save_tables(tables: dict[str, pd.DataFrame]) -> None:
    for name, table in tables.items():
        table.to_csv(TABLES_DIR / f"{name}.csv", index=False)
    with pd.ExcelWriter(TABLES_DIR / "analysis_tables.xlsx") as writer:
        for name, table in tables.items():
            table.to_excel(writer, sheet_name=name[:31], index=False)


def save_latex_tables(tables: dict[str, pd.DataFrame]) -> None:
    for name in ["dataset_overview", "attribute_coverage", "missing_values", "long_tail_labels"]:
        table = tables.get(name)
        if table is not None and not table.empty:
            (TABLES_DIR / f"{name}.tex").write_text(simple_latex_table(table.head(40)), encoding="utf-8")


def escape_latex(value: Any) -> str:
    text = str(value)
    replacements = {
        "\\": r"\textbackslash{}",
        "&": r"\&",
        "%": r"\%",
        "$": r"\$",
        "#": r"\#",
        "_": r"\_",
        "{": r"\{",
        "}": r"\}",
        "~": r"\textasciitilde{}",
        "^": r"\textasciicircum{}",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return text


def simple_latex_table(table: pd.DataFrame) -> str:
    """Render a small tabular without optional pandas styling dependencies."""
    columns = list(table.columns)
    alignment = "l" * len(columns)
    lines = [rf"\begin{{tabular}}{{{alignment}}}", r"\hline"]
    lines.append(" & ".join(escape_latex(column) for column in columns) + r" \\")
    lines.append(r"\hline")
    for _, row in table.iterrows():
        lines.append(" & ".join(escape_latex(row[column]) for column in columns) + r" \\")
    lines.extend([r"\hline", r"\end{tabular}", ""])
    return "\n".join(lines)


def save_figures(tables: dict[str, pd.DataFrame], classification_summary: pd.DataFrame) -> None:
    plt.rcParams.update(
        {
            "axes.grid": True,
            "grid.alpha": 0.25,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "figure.facecolor": "white",
            "axes.facecolor": "white",
            "font.size": 10,
        }
    )

    overview = tables["dataset_overview"]
    fig, ax = plt.subplots(figsize=(9, 5))
    plot_data = overview[overview["dataset"].isin(["pwc_single_label_with_somef", "pwc_multi_label_with_somef", "biotools_single_label_with_somef", "biotools_multi_label_with_somef"])]
    ax.barh(plot_data["dataset"], plot_data["records"], color="#4c78a8")
    ax.set_xlabel("Records")
    ax.set_ylabel("")
    ax.set_title("Processed Dataset Sizes")
    ax.invert_yaxis()
    fig.tight_layout()
    save_figure(fig, "dataset_size_comparison")

    coverage = tables["attribute_coverage"]
    focus = coverage[coverage["dataset"].eq("with_somef") & coverage["attribute"].isin(["paper_title", "paper_abstract", "readme_content", "somef_description", "github_keywords", "repository_metadata"])]
    fig, ax = plt.subplots(figsize=(10, 5.5))
    pivot = focus.pivot(index="attribute", columns="source", values="coverage_percent").fillna(0)
    pivot.plot(kind="barh", ax=ax, width=0.8)
    ax.set_xlabel("Coverage (%)")
    ax.set_ylabel("")
    ax.set_title("Attribute Coverage by Source")
    ax.legend(title="Source")
    fig.tight_layout()
    save_figure(fig, "attribute_coverage")

    labels = tables["label_distribution"].groupby("source", as_index=False).head(20)
    fig, axes = plt.subplots(nrows=max(1, labels["source"].nunique()), ncols=1, figsize=(10, 8), squeeze=False)
    for ax, (source, group) in zip(axes.ravel(), labels.groupby("source")):
        group = group.sort_values("support", ascending=True)
        ax.barh(group["label"], group["support"], color="#59a14f")
        ax.set_title(f"Top Labels: {source}")
        ax.set_xlabel("Support")
        ax.set_ylabel("")
    fig.tight_layout()
    save_figure(fig, "label_distribution")

    missing = tables["missing_values"].set_index("field")[["missing_percent"]]
    fig, ax = plt.subplots(figsize=(6, max(4, len(missing) * 0.28)))
    values = missing["missing_percent"].to_numpy().reshape(-1, 1)
    image = ax.imshow(values, aspect="auto", cmap="Blues", vmin=0, vmax=100)
    ax.set_yticks(np.arange(len(missing.index)))
    ax.set_yticklabels(missing.index)
    ax.set_xticks([0])
    ax.set_xticklabels(["Missing (%)"])
    for idx, value in enumerate(missing["missing_percent"]):
        ax.text(0, idx, f"{value:.1f}", ha="center", va="center", color="black")
    fig.colorbar(image, ax=ax, label="Missing (%)")
    ax.set_title("Missing Value Summary")
    ax.set_ylabel("")
    fig.tight_layout()
    save_figure(fig, "missing_value_heatmap")

    if not classification_summary.empty and {"fold_id", "dataset_name", "attribute_combination", "model_name"}.issubset(classification_summary.columns):
        cls = classification_summary[classification_summary["fold_id"].eq("train_test")].copy()
        metric = "f1_macro" if "f1_macro" in cls.columns else "f1_macro_mean"
        if metric in cls.columns and not cls.empty:
            cls["experiment"] = cls["attribute_combination"] + "\n" + cls["model_name"]
            cls = cls.sort_values(metric, ascending=False).groupby("dataset_name", as_index=False).head(8)
            fig, ax = plt.subplots(figsize=(12, 6))
            labels = cls["dataset_name"] + " | " + cls["experiment"]
            ax.barh(labels, cls[metric], color="#e15759")
            ax.set_xlabel(metric.replace("_", " ").title())
            ax.set_ylabel("")
            ax.set_title("Best Local Classification Results")
            ax.invert_yaxis()
            fig.tight_layout()
            save_figure(fig, "classification_performance")


def save_figure(fig: plt.Figure, name: str) -> None:
    fig.savefig(FIGURES_DIR / f"{name}.png", dpi=300, bbox_inches="tight")
    fig.savefig(FIGURES_DIR / f"{name}.pdf", bbox_inches="tight")
    plt.close(fig)


def run_local_training(skip_training: bool) -> None:
    if skip_training:
        LOGGER.info("Skipping training rerun by request; existing saved metrics will be summarized.")
        return
    LOGGER.info("Rerunning local TF-IDF training experiments on the full SOMEF-enriched dataset")
    subprocess.run([sys.executable, str(TRAINING_SCRIPT)], cwd=ROOT, check=True)


def write_summary_report(tables: dict[str, pd.DataFrame], classification_best: pd.DataFrame, skip_training: bool) -> None:
    overview = tables["dataset_overview"].set_index("dataset")
    combined = overview.loc["combined_all_with_somef"]
    coverage = tables["attribute_coverage"]
    readme_cov = coverage[(coverage["dataset"] == "with_somef") & (coverage["attribute"] == "readme_content")]
    somef_cov = coverage[(coverage["dataset"] == "with_somef") & (coverage["attribute"] == "somef_description")]
    best_lines = "No classification results were available."
    if not classification_best.empty:
        cols = [col for col in ["source_dataset", "label_setting", "dataset_name", "attribute_combination", "model_name", "f1_macro", "accuracy", "subset_accuracy"] if col in classification_best.columns]
        best_lines = simple_markdown_table(classification_best[cols].head(12))
    report = f"""# Analysis Summary

Generated: {datetime.now().isoformat(timespec="seconds")}

## Key dataset statistics

- Combined SOMEF-enriched records: {int(combined["records"]):,}
- Records with GitHub links: {int(combined["records_with_github_links"]):,}
- Records with README content: {int(combined["records_with_readme"]):,}
- Records with SOMEF descriptions: {int(combined["records_with_somef_description"]):,}
- Records with title or abstract: {int(combined["records_with_title_or_abstract"]):,}

## Key coverage findings

{simple_markdown_table(readme_cov)}

{simple_markdown_table(somef_cov)}

## Key classification findings

Training rerun skipped for this report refresh: `{skip_training}`.
Classification metrics source: `{(config.RESULTS_DIR / "training" / "summary_results.csv").relative_to(ROOT)}`.

{best_lines}

## Main takeaways and limitations

- The reproducible analysis is local-only and uses saved PwC, bio.tools, merged, README, and SOMEF files.
- bio.tools labels are mapped to the highest meaningful EDAM topic categories below the EDAM Topic root for the final analysis.
- External collection/enrichment steps are intentionally skipped in this workflow.
- Classification results come from the full-dataset local TF-IDF baseline script and its deterministic train/test splits.
- Missing metadata is uneven across sources, so coverage tables should be cited together with model comparisons.
"""
    SUMMARY_REPORT.write_text(report, encoding="utf-8")


def simple_markdown_table(table: pd.DataFrame) -> str:
    if table.empty:
        return "No rows."
    columns = list(table.columns)
    lines = [
        "| " + " | ".join(str(column) for column in columns) + " |",
        "| " + " | ".join("---" for _ in columns) + " |",
    ]
    for _, row in table.iterrows():
        lines.append("| " + " | ".join(str(row[column]) for column in columns) + " |")
    return "\n".join(lines)


def write_run_config(skip_training: bool) -> None:
    write_json(
        {
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "random_seed": config.RANDOM_SEED,
            "skip_training": skip_training,
            "local_only": True,
            "external_steps_skipped": [
                "rerun_somef",
                "download_papers_with_code",
                "download_biotools",
                "query_github",
                "query_openalex",
                "external_embedding_apis",
            ],
            "inputs": {name: str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path) for name, path in {**RAW_AND_INTERIM_INPUTS, **DATASET_INPUTS}.items()},
            "outputs": {
                "processed": str(PROCESSED_DIR.relative_to(ROOT)),
                "tables": str(TABLES_DIR.relative_to(ROOT)),
                "figures": str(FIGURES_DIR.relative_to(ROOT)),
                "reports": str(REPORTS_DIR.relative_to(ROOT)),
                "log": str(RUN_LOG.relative_to(ROOT)),
            },
        },
        RUN_CONFIG,
    )


def main() -> None:
    args = parse_args()
    configure_script_logging()
    ensure_output_dirs()
    LOGGER.info("Starting full local-only analysis")
    require_local_inputs()
    write_run_config(args.skip_training)
    datasets = save_processed_datasets()

    before_somef = datasets["combined_all"]
    with_somef = datasets["combined_all_with_somef"]
    overview = dataset_overview_table(datasets)
    attribute_coverage = pd.concat(
        [coverage_table(before_somef, "before_somef"), coverage_table(with_somef, "with_somef")],
        ignore_index=True,
    )
    labels = label_distribution_table(with_somef)
    tables = {
        "dataset_overview": overview,
        "attribute_coverage": attribute_coverage,
        "missing_values": missing_value_table(with_somef),
        "label_distribution": labels,
        "long_tail_labels": long_tail_table(labels),
        "pwc_vs_biotools_comparison": overview[overview["dataset"].isin(["pwc_multi_label_with_somef", "biotools_multi_label_with_somef"])],
    }

    run_local_training(args.skip_training)
    classification_summary, classification_best = classification_tables()
    if not classification_summary.empty:
        tables["classification_results"] = classification_summary
    if not classification_best.empty:
        tables["best_attribute_model_combinations"] = classification_best

    save_tables(tables)
    save_latex_tables(tables)
    save_figures(tables, classification_summary)
    write_summary_report(tables, classification_best, args.skip_training)
    LOGGER.info("Full local-only analysis complete")


if __name__ == "__main__":
    main()
