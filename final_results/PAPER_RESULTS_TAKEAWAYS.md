# Final Results: Paper-Oriented Takeaways

Generated from the final result package in `final_results/` using the final curated datasets in `final_datasets/`.

## What Was Evaluated

The final analysis uses six training/evaluation datasets: three derived from Papers with Code and three derived from bio.tools. For each source, the experiments separate records with exactly one label, records with multiple labels only, and a merged dataset containing both single-label and multi-label records. The merged datasets are evaluated as multi-label classification problems.

| Dataset | Source | Label setting | Records | Labels | Train | Test |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| `pwc_single_only` | Papers with Code | single-label | 37,058 | 6 | 29,646 | 7,412 |
| `pwc_multi_only` | Papers with Code | multi-label only | 5,611 | 6 | 4,488 | 1,123 |
| `pwc_merged` | Papers with Code | merged multi-label | 42,669 | 6 | 34,135 | 8,534 |
| `biotools_single_only` | bio.tools | single-label | 3,272 | 11 | 2,617 | 655 |
| `biotools_multi_only` | bio.tools | multi-label only | 10,878 | 12 | 8,702 | 2,176 |
| `biotools_merged` | bio.tools | merged multi-label | 14,150 | 12 | 11,320 | 2,830 |

The final combined data package contains 56,819 total records: 42,669 from Papers with Code and 14,150 from bio.tools. README content is available for 54,893 records, SOMEF descriptions for 48,300 records, and either a title or abstract for 56,743 records.

## Evaluation Setup

All reported numbers in `classification_results.csv` are from a deterministic 80/20 train/test split with random seed 42. The same split is reused within each dataset across all attribute combinations and all model pipelines, so model and attribute comparisons are paired within a dataset.

The final run contains 240 completed classification rows and zero failed rows: 6 datasets x 8 usable attribute sets x 5 pipelines. The originally planned `keywords_only` setting was not trainable because keyword coverage is 0% for both sources in the final data. Cross-validation was not run in this final package (`cv_summary.csv` is empty); the script supports `--folds 3` or `--folds 5` for a future fold-based robustness run.

The implemented local pipelines are:

| Pipeline | Description |
| --- | --- |
| `tfidf_logistic_regression` | TF-IDF unigrams/bigrams with a balanced logistic-loss linear classifier. |
| `tfidf_linear_svm` | TF-IDF unigrams/bigrams with balanced Linear SVM. |
| `tfidf_random_forest` | TF-IDF unigrams/bigrams with balanced Random Forest. |
| `tfidf_xgboost` | TF-IDF unigrams/bigrams with XGBoost. |
| `tfidf_hard_voting` | Majority-vote ensemble over logistic regression, Linear SVM, and Random Forest. |

The final result package should be interpreted as the local classical ML evaluation. Neural embedding, fine-tuned transformer, and LLM prompting experiments are not included in the reported comparison table and should only be added to the paper after they are run under a separately documented setup.

## Overall Best Results

The strongest results are obtained on Papers with Code, especially when all available metadata is used. bio.tools is substantially harder, particularly in macro-F1, because it has more labels, stronger imbalance, and several low-support categories.

| Dataset | Best attribute set | Best pipeline | Macro-F1 | Micro-F1 | Weighted-F1 | Accuracy / Subset accuracy |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| `pwc_multi_only` | `all_available_metadata` | `tfidf_xgboost` | 0.9589 | 0.9736 | 0.9735 | 0.9056 subset accuracy |
| `pwc_single_only` | `all_available_metadata` | `tfidf_xgboost` | 0.8906 | 0.9753 | 0.9749 | 0.9753 accuracy |
| `pwc_merged` | `all_available_metadata` | `tfidf_xgboost` | 0.8581 | 0.9565 | 0.9555 | 0.9107 subset accuracy |
| `biotools_multi_only` | `all_publication_metadata` | `tfidf_hard_voting` | 0.5596 | 0.7885 | 0.7919 | 0.3801 subset accuracy |
| `biotools_merged` | `all_available_metadata` | `tfidf_hard_voting` | 0.5371 | 0.7721 | 0.7808 | 0.3862 subset accuracy |
| `biotools_single_only` | `all_available_metadata` | `tfidf_linear_svm` | 0.4266 | 0.9099 | 0.9030 | 0.9099 accuracy |

Main interpretation: PwC labels are strongly recoverable from textual and repository metadata, while bio.tools labels are only moderately recoverable, with high micro/weighted scores but much lower macro-F1. This gap indicates that bio.tools performance is dominated by strong prediction of frequent classes while rare classes remain difficult.

## Source-Level Takeaways

### Papers with Code

Papers with Code shows consistently high classification performance. The best results are achieved with `all_available_metadata`, where XGBoost reaches macro-F1 0.8906 for single-label records, 0.9589 for multi-label-only records, and 0.8581 for the merged multi-label dataset.

The multi-label-only PwC dataset performs surprisingly well. This likely reflects that multi-label PwC records contain richer or more explicit metadata and that the six-label space is relatively compact. In the best multi-label-only setting, XGBoost obtains macro-F1 0.9589, micro-F1 0.9736, weighted-F1 0.9735, subset accuracy 0.9056, and hamming loss 0.0181.

The merged PwC dataset remains strong but is lower than the multi-label-only subset in macro-F1. The best merged result is macro-F1 0.8581. This suggests that combining single-label and multi-label records increases heterogeneity: many single-label records may provide less complete evidence for secondary categories, while multi-label training requires the model to learn both primary and co-occurring labels.

### bio.tools

bio.tools is notably more difficult. The best macro-F1 values are 0.5596 for multi-label-only records, 0.5371 for the merged dataset, and 0.4266 for single-label records. These results are much lower than PwC despite reasonable micro-F1 and weighted-F1 values.

The difference between macro-F1 and weighted/micro-F1 is especially important for bio.tools. For example, the best bio.tools single-label model reaches accuracy 0.9099 and weighted-F1 0.9030, but macro-F1 is only 0.4266. This means the model performs well on dominant labels, especially Biosciences, but struggles with low-support labels.

For bio.tools multi-label tasks, the hard-voting ensemble is the most reliable pipeline. It wins 7 of 8 attribute settings for both `biotools_multi_only` and `biotools_merged`. This suggests that combining complementary linear and tree-based decisions is more robust for the noisier and more imbalanced bio.tools label space than relying on XGBoost alone.

## Pipeline Comparison

Mean macro-F1 by source and label setting shows different model behavior across the two data sources.

| Source | Label setting | Best mean pipeline | Mean macro-F1 | Max macro-F1 |
| --- | --- | --- | ---: | ---: |
| Papers with Code | single-label | `tfidf_hard_voting` | 0.6152 | 0.7704 |
| Papers with Code | multi-label | `tfidf_hard_voting` | 0.6826 | 0.8769 |
| bio.tools | single-label | `tfidf_linear_svm` | 0.3359 | 0.4266 |
| bio.tools | multi-label | `tfidf_hard_voting` | 0.4734 | 0.5596 |

XGBoost gives the best individual top-line results for the PwC all-metadata settings, but it is not uniformly best across all attributes. For PwC single-label, hard voting wins 4 of 8 attribute settings; XGBoost wins only the all-available metadata setting. For PwC multi-label-only, XGBoost wins 5 of 8 attribute settings and dominates the strongest metadata-rich condition.

For bio.tools, XGBoost is not the strongest overall. Its mean macro-F1 is lower than hard voting, Linear SVM, and logistic regression for bio.tools multi-label tasks, and it performs worst on average for bio.tools single-label tasks. This pattern suggests that XGBoost benefits from strong, relatively separable PwC metadata but is less stable under bio.tools imbalance and label heterogeneity.

Random Forest generally underperforms the linear models and voting ensemble in macro-F1, especially for bio.tools. It sometimes has competitive micro-F1 or weighted-F1, but this is often because it favors frequent labels and does not recover rare labels well.

## Attribute-Set Comparison

Metadata-rich combinations are consistently strongest. `all_available_metadata` is the best setting for all three PwC datasets, for bio.tools single-label, and for bio.tools merged. For bio.tools multi-label-only, `all_publication_metadata` narrowly outperforms `all_available_metadata`.

| Source | Label setting | Best mean attribute set | Mean macro-F1 | Best macro-F1 in that setting |
| --- | --- | --- | ---: | ---: |
| Papers with Code | single-label | `all_available_metadata` | 0.7768 | 0.8906 |
| Papers with Code | multi-label | `all_available_metadata` | 0.8272 | 0.9589 |
| bio.tools | single-label | `all_available_metadata` | 0.3391 | 0.4266 |
| bio.tools | multi-label | `all_publication_metadata` | 0.4956 | 0.5596 |

Abstract-only features are strong for PwC. On `pwc_multi_only`, XGBoost with `abstract_only` reaches macro-F1 0.8468, micro-F1 0.9040, and subset accuracy 0.7115. On `pwc_single_only`, the best abstract-only model reaches macro-F1 0.7249. This supports the claim that paper abstracts alone contain substantial signal about computational task/category labels.

Repository-only metadata is weaker than publication metadata. The `repository_title_keywords` setting is the weakest usable setting across both sources. For example, its best macro-F1 is only 0.2727 for `pwc_single_only`, 0.4835 for `pwc_multi_only`, 0.2164 for `biotools_single_only`, and 0.2373 for `biotools_multi_only`. Repository title plus keyword-style metadata alone is therefore insufficient for reliable classification.

README/description metadata helps, but not always as much as expected. For PwC, `abstract_readme_description` is weaker than `abstract_only` and `all_publication_metadata` in the best-model comparisons. For bio.tools multi-label, `abstract_readme_description` is one of the strongest settings, reaching macro-F1 0.5485 with hard voting. This suggests README/description text is more useful when publication-style metadata is sparse or less directly aligned with labels.

## Label Imbalance and Per-Class Behavior

Both sources are imbalanced, but the imbalance is more damaging for bio.tools because there are more labels and several very small classes.

Papers with Code label assignments are dominated by Computer Vision and Natural Language Processing:

| PwC label | Assignments | Share of assignments |
| --- | ---: | ---: |
| Computer Vision | 22,138 | 45.49% |
| Natural Language Processing | 16,585 | 34.08% |
| Graphs | 5,220 | 10.73% |
| Sequential | 2,287 | 4.70% |
| Reinforcement Learning | 2,210 | 4.54% |
| Audio | 222 | 0.46% |

bio.tools is dominated by Biosciences and Data acquisition:

| bio.tools label | Assignments | Share of assignments |
| --- | ---: | ---: |
| Biosciences | 13,234 | 43.46% |
| Data acquisition | 6,801 | 22.33% |
| Computer science | 3,176 | 10.43% |
| Data management | 1,869 | 6.14% |
| Informatics | 1,145 | 3.76% |
| Environmental sciences | 1,096 | 3.60% |
| Mathematics | 1,016 | 3.34% |
| Chemistry | 756 | 2.48% |
| Experimental design and studies | 626 | 2.06% |
| Literature and language | 456 | 1.50% |
| Physics | 258 | 0.85% |
| Open science | 21 | 0.07% |

The minority-class issue is visible in per-class results. In the best PwC single-label model, Audio has precision 1.0000 but recall only 0.3846, giving F1 0.5556. In the best PwC merged model, Audio recall drops to 0.2821 and F1 to 0.4400. This indicates that Audio predictions are conservative: when the model predicts Audio it is usually correct, but many true Audio examples are missed.

Reinforcement Learning is better recovered than Audio but remains weaker than majority labels. In the best PwC merged model, Reinforcement Learning has F1 0.8854, while Computer Vision and Natural Language Processing have F1 0.9596 and 0.9715, respectively.

For bio.tools, the rarest label, Open science, has F1 0.0000 in the best multi-label models because there are only 4-5 Open science examples in the test split. Physics also remains difficult, with F1 0.3333 in the best bio.tools multi-label-only model and 0.2947 in the best merged model. In contrast, Biosciences is classified very well, with F1 0.9573 in the best bio.tools multi-label-only model and 0.9441 in the best merged model.

These per-class patterns strongly support reporting macro-F1 alongside micro-F1 and weighted-F1. Micro/weighted scores can look high even when rare categories are poorly recovered.

## Single-Label vs Multi-Label Findings

The single-label and multi-label-only datasets are disjoint by construction: the single-label dataset contains records with exactly one label, while the multi-label-only dataset contains records with two or more labels. The merged dataset contains both groups.

For PwC, multi-label-only classification performs best. The best multi-label-only macro-F1 is 0.9589, compared with 0.8906 for single-label and 0.8581 for merged. This should not be interpreted as multi-label classification being inherently easier; instead, it suggests that the multi-label PwC records are likely richer, more explicit, or more consistently annotated.

For bio.tools, multi-label-only also outperforms single-label in macro-F1: 0.5596 versus 0.4266. However, the difference is smaller and the merged dataset remains similar to multi-label-only at 0.5371. This suggests that bio.tools label difficulty is driven less by single-vs-multi structure and more by label imbalance, label granularity, and heterogeneous metadata quality.

## Paper-Ready Main Claims

1. The final experiments show that metadata-based classification is feasible, but performance depends strongly on the source dataset and label distribution.

2. Papers with Code labels are highly predictable from textual and repository metadata, with best macro-F1 values above 0.85 for all three PwC settings and 0.9589 for the multi-label-only subset.

3. bio.tools classification is substantially harder. Although accuracy, micro-F1, and weighted-F1 are often high, macro-F1 remains below 0.56, showing that rare categories are not reliably recovered.

4. The best overall attribute setting is usually `all_available_metadata`, indicating that combining publication text, software metadata, repository metadata, README/SOMEF-derived descriptions, tasks, methods, and secondary metadata provides the richest signal.

5. Publication-oriented metadata is more informative than repository-title/keyword metadata alone. Abstracts and paper metadata provide strong classification signal, especially for Papers with Code.

6. Ensemble voting is robust, especially for bio.tools. XGBoost provides the best peak results for PwC but is not consistently best for bio.tools.

7. Rare classes remain the main limitation. Audio in PwC and Open science/Physics in bio.tools show substantially weaker recall/F1 than majority classes.

8. Macro-F1 should be emphasized in the paper because it exposes poor rare-class performance that is hidden by high accuracy, micro-F1, or weighted-F1.

## Recommended Wording for the Paper

The final evaluation used deterministic 80/20 train/test splits with identical splits across attribute configurations and model pipelines within each dataset. This allows direct comparison of feature groups and models while avoiding split-induced variation. Across 240 completed local classical experiments, the strongest results were obtained for Papers with Code, where XGBoost with all available metadata achieved macro-F1 of 0.8906 for single-label classification, 0.9589 for multi-label-only classification, and 0.8581 for the merged multi-label setting.

In contrast, bio.tools showed lower macro-F1 despite high accuracy and weighted-F1, indicating that the models performed well on dominant labels but struggled with low-support categories. The best bio.tools results were obtained with a hard-voting ensemble, reaching macro-F1 of 0.5596 for multi-label-only records and 0.5371 for the merged dataset. For single-label bio.tools records, Linear SVM with all available metadata achieved the best macro-F1 of 0.4266.

These results suggest that research software category prediction is strongly dependent on the metadata source, label space, and class distribution. Publication metadata and combined metadata provide the strongest signal, while repository-title/keyword metadata alone is insufficient. The per-class results further show that minority labels such as Audio, Open science, and Physics remain challenging, motivating future work on imbalance-aware training, richer semantic representations, and possibly source-specific modeling strategies.

## Important Caveats

- The final package reports one deterministic train/test split. Standard deviations or confidence intervals require rerunning with `--folds 3` or `--folds 5`.
- `all_available_metadata` is the most informative setting, but it should be interpreted as a metadata-rich upper-bound condition because it combines many fields.
- The 0% keyword coverage means `keywords_only` could not be evaluated as a standalone feature setting in this final run.
- The current result package compares local classical pipelines only. Neural embedding, fine-tuned transformer, and LLM prompting baselines should be reported separately if they are added later.
- Macro-F1 is the most important metric for claims about balanced category performance because the datasets are substantially imbalanced.
