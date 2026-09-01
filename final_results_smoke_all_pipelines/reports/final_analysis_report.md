# Final Analysis Report

Generated: 2026-07-01T01:17:59

Training skipped for this run: `False`.

## Summary

- Final combined records: 56,819
- Records with README content: 54,893
- Records with SOMEF descriptions: 48,300
- Records with title or abstract: 56,743
- Training datasets: PwC single-only, PwC multi-only, PwC merged, bio.tools single-only, bio.tools multi-only, and bio.tools merged.
- Train/test evaluation: deterministic 80/20 split with random seed 42; the same split is reused across every attribute set and every model within a dataset.
- Cross-validation: `0` folds were requested. Fold-level means and standard deviations are written to `final_results/tables/cv_summary.csv` when folds are greater than 1.
- Metrics: macro-F1, micro-F1, weighted-F1, precision/recall, plus accuracy for single-label and subset accuracy/hamming loss for multi-label.
- Model protocol: no model is fine-tuned. `simple` models use TF-IDF; `bert` models use frozen Hugging Face encoder embeddings plus simple classifiers; `openai_*` models use deterministic structured prompts and require `--enable-openai`.

## Dataset Overview

| dataset | records | sources | papers_with_code_records | biotools_records | unique_labels_total | records_with_readme | records_with_somef_description | records_with_title_or_abstract |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| final_single_label | 40330 | bio.tools, papers_with_code | 37058 | 3272 | 17 | 39080 | 34135 | 40305 |
| final_multi_label_only | 16489 | bio.tools, papers_with_code | 5611 | 10878 | 18 | 15813 | 14165 | 16438 |
| final_combined | 56819 | bio.tools, papers_with_code | 42669 | 14150 | 18 | 54893 | 48300 | 56743 |

## Best Train/Test Results

| dataset_name | label_setting | attribute_set | model_name | f1_macro | f1_micro | f1_weighted | accuracy |
| --- | --- | --- | --- | --- | --- | --- | --- |
| pwc_single_only | single | abstract_only | openai_few_shot | 1.0 | 1.0 | 1.0 | 1.0 |
| pwc_single_only | single | abstract_only | openai_zero_shot | 1.0 | 1.0 | 1.0 | 1.0 |
| pwc_single_only | single | abstract_only | scibert_embedding_logistic_regression | 0.3333333333333333 | 0.5 | 0.5 | 0.5 |
| pwc_single_only | single | abstract_only | modernbert_embedding_random_forest | 0.3333333333333333 | 0.5 | 0.5 | 0.5 |
| pwc_single_only | single | abstract_only | modernbert_embedding_logistic_regression | 0.3333333333333333 | 0.5 | 0.5 | 0.5 |

## Output Files

- Tables: `final_results/tables/`
- Figures: `final_results/figures/`
- Predictions: `final_results/predictions/predictions.jsonl`
- Splits: `final_results/splits/`
- Report: `final_results/reports/final_analysis_report.md`
- Implementation README: `final_results/README.md`
