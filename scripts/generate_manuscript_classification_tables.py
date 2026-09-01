#!/usr/bin/env python3
"""Generate manuscript LaTeX tables from completed classification outputs."""
from __future__ import annotations

import csv
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent.parent
INPUT = ROOT / "results" / "training" / "summary_results.csv"
TABLES_DIR = ROOT / "results" / "tables"


ATTRIBUTE_LABELS = {
    "abstract_only": "Abstract",
    "title_only": "Title",
    "repository_title_keywords": "Repository title/keywords",
    "abstract_readme_description": "Abstract + README/description",
    "abstract_repository_title_keywords": "Abstract + repository title/keywords",
    "all_publication_metadata": "Publication metadata",
    "all_repository_metadata": "Repository metadata",
    "all_non_target_textual_metadata": "All non-target textual metadata",
}

DATASET_LABELS = {
    "papers_single_label": "PwC single-label",
    "papers_multi_label": "PwC multi-label",
    "biotools_single_label": "bio.tools single-label",
    "biotools_multi_label": "bio.tools multi-label",
}


def rows() -> list[dict[str, str]]:
    with INPUT.open("r", encoding="utf-8", newline="") as handle:
        return [row for row in csv.DictReader(handle)]


def f4(value: Any) -> str:
    if value in (None, "", "nan"):
        return "--"
    return f"{float(value):.4f}"


def pct(value: Any) -> str:
    if value in (None, "", "nan"):
        return "--"
    return f"{float(value):.4f}"


def metric_row(row: dict[str, str]) -> dict[str, str]:
    label_setting = row["label_setting"]
    return {
        "dataset": DATASET_LABELS[row["dataset_name"]],
        "attribute": ATTRIBUTE_LABELS[row["attribute_combination"]],
        "records": f"{int(row['num_records']):,}",
        "train": f"{int(row['num_train']):,}",
        "test": f"{int(row['num_test']):,}",
        "labels": row["num_labels"],
        "f1_macro": f4(row["f1_macro"]),
        "f1_micro": f4(row["f1_micro"]),
        "f1_weighted": f4(row["f1_weighted"]),
        "accuracy": f4(row["accuracy"] if label_setting == "single" else row["subset_accuracy"]),
        "accuracy_label": "Accuracy" if label_setting == "single" else "Subset accuracy",
    }


def best_by_dataset(data: list[dict[str, str]]) -> list[dict[str, str]]:
    best = {}
    for row in data:
        key = row["dataset_name"]
        if key not in best or float(row["f1_macro"]) > float(best[key]["f1_macro"]):
            best[key] = row
    return [metric_row(best[key]) for key in ["papers_single_label", "papers_multi_label", "biotools_single_label", "biotools_multi_label"]]


def attribute_comparison(data: list[dict[str, str]]) -> list[dict[str, str]]:
    return [metric_row(row) for row in data]


def latex_escape(text: str) -> str:
    return (
        text.replace("\\", r"\textbackslash{}")
        .replace("&", r"\&")
        .replace("%", r"\%")
        .replace("$", r"\$")
        .replace("#", r"\#")
        .replace("_", r"\_")
        .replace("{", r"\{")
        .replace("}", r"\}")
    )


def write_task_table(data: list[dict[str, str]]) -> None:
    seen = {}
    for row in data:
        seen[row["dataset_name"]] = row
    ordered = [seen[key] for key in ["papers_single_label", "papers_multi_label", "biotools_single_label", "biotools_multi_label"]]
    lines = [
        r"\begin{table}[htbp]",
        r"\centering",
        r"\small",
        r"\caption{Classification datasets used in the completed TF--IDF LinearSVC experiments.}",
        r"\label{tab:classification-datasets}",
        r"\begin{tabular}{lrrrr}",
        r"\toprule",
        r"Dataset & Records & Train & Test & Labels \\",
        r"\midrule",
    ]
    for row in ordered:
        lines.append(
            f"{DATASET_LABELS[row['dataset_name']]} & {int(row['num_records']):,} & {int(row['num_train']):,} & {int(row['num_test']):,} & {row['num_labels']} \\\\"
        )
    lines.extend([r"\bottomrule", r"\end{tabular}", r"\end{table}", ""])
    (TABLES_DIR / "classification_dataset_overview.tex").write_text("\n".join(lines), encoding="utf-8")


def write_best_table(data: list[dict[str, str]]) -> None:
    lines = [
        r"\begin{table}[htbp]",
        r"\centering",
        r"\small",
        r"\caption{Best completed classification result for each dataset, selected by macro-F1.}",
        r"\label{tab:classification-best-results}",
        r"\begin{tabular}{llrrrr}",
        r"\toprule",
        r"Dataset & Attribute Set & Macro-F1 & Micro-F1 & Weighted-F1 & Accuracy/Sub.Acc. \\",
        r"\midrule",
    ]
    for row in best_by_dataset(data):
        lines.append(
            f"{latex_escape(row['dataset'])} & {latex_escape(row['attribute'])} & {row['f1_macro']} & {row['f1_micro']} & {row['f1_weighted']} & {row['accuracy']} \\\\"
        )
    lines.extend([r"\bottomrule", r"\end{tabular}", r"\end{table}", ""])
    (TABLES_DIR / "classification_best_results.tex").write_text("\n".join(lines), encoding="utf-8")


def write_attribute_table(data: list[dict[str, str]]) -> None:
    lines = [
        r"\begin{table}[htbp]",
        r"\centering",
        r"\scriptsize",
        r"\caption{Macro-F1 of completed TF--IDF LinearSVC experiments by dataset and metadata attribute set.}",
        r"\label{tab:classification-attribute-comparison}",
        r"\setlength{\tabcolsep}{3pt}",
        r"\begin{tabular}{lrrrr}",
        r"\toprule",
        r"Attribute Set & PwC Single & PwC Multi & bio.tools Single & bio.tools Multi \\",
        r"\midrule",
    ]
    lookup = {(row["dataset_name"], row["attribute_combination"]): row for row in data}
    for attribute, label in ATTRIBUTE_LABELS.items():
        values = [
            f4(lookup[(dataset, attribute)]["f1_macro"])
            for dataset in ["papers_single_label", "papers_multi_label", "biotools_single_label", "biotools_multi_label"]
        ]
        lines.append(f"{latex_escape(label)} & {' & '.join(values)} \\\\")
    lines.extend([r"\bottomrule", r"\end{tabular}", r"\end{table}", ""])
    (TABLES_DIR / "classification_attribute_comparison.tex").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    TABLES_DIR.mkdir(parents=True, exist_ok=True)
    data = rows()
    write_task_table(data)
    write_best_table(data)
    write_attribute_table(data)


if __name__ == "__main__":
    main()
