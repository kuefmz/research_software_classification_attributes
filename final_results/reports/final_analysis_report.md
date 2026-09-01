# Final Analysis Report

Generated: 2026-07-13T12:22:56

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
- Model protocol: transformer parameters are never updated. `simple` models use TF-IDF; `bert` models use frozen Hugging Face encoder embeddings plus simple classifiers; `local_llm_*` models use deterministic structured prompts against a local instruction-tuned runtime and require `--enable-local-llm`.

## Dataset Overview

| dataset | records | sources | papers_with_code_records | biotools_records | unique_labels_total | records_with_readme | records_with_somef_description | records_with_title_or_abstract |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| final_single_label | 40330 | bio.tools, papers_with_code | 37058 | 3272 | 17 | 39080 | 34135 | 40305 |
| final_multi_label_only | 16489 | bio.tools, papers_with_code | 5611 | 10878 | 18 | 15813 | 14165 | 16438 |
| final_combined | 56819 | bio.tools, papers_with_code | 42669 | 14150 | 18 | 54893 | 48300 | 56743 |

## Best Train/Test Results

| dataset_name | label_setting | attribute_set | model_name | f1_macro | f1_micro | f1_weighted | accuracy |
| --- | --- | --- | --- | --- | --- | --- | --- |
| pwc_single_only | single | abstract_only | tfidf_linear_svm | 0.7248847124268765 | 0.8687263896384242 | 0.869123179013157 | 0.8687263896384242 |
| pwc_single_only | single | abstract_only | tfidf_hard_voting | 0.7142759425082139 | 0.8672423097679439 | 0.8668284052429149 | 0.8672423097679439 |
| pwc_single_only | single | abstract_only | tfidf_xgboost | 0.6705274545114334 | 0.8764166216945494 | 0.87224154589437 | 0.8764166216945494 |
| pwc_single_only | single | abstract_only | tfidf_logistic_regression | 0.6468074155724751 | 0.8175930922827847 | 0.8210040305470729 | 0.8175930922827847 |
| pwc_single_only | single | abstract_only | tfidf_random_forest | 0.6282487600434606 | 0.8619805720453318 | 0.8549819297203098 | 0.8619805720453318 |

## Output Files

- Tables: `final_results/tables/`
- Figures: `final_results/figures/`
- Predictions: `final_results/predictions/predictions.jsonl`
- Splits: `final_results/splits/`
- Report: `final_results/reports/final_analysis_report.md`
- Implementation README: `final_results/README.md`
