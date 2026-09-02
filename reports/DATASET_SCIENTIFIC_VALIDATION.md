# Dataset Scientific Validation

## Dataset Identity

The build creates a GitHub-backed Research Software analysis cohort plus Level
1 and Level 2 views from frozen local inputs. It is not a complete Papers with
Code or bio.tools population, and it is not a final immutable release until
human review approves the scientific decisions.

## Unit Of Analysis

PwC rows represent source paper records. bio.tools rows represent tool
observations, expanded to tool-publication observations where DOI values exist.

## Source Provenance

PwC input: `/home/jenifer/github/research_software_classification_attributes/data/pwc_merged/pwc_merged_relevant_attributes.jsonl`.
bio.tools input: `/home/jenifer/github/research_software_classification_attributes/data/biotools/biotools_flat_all.csv` plus `/home/jenifer/github/research_software_classification_attributes/data/biotools/biotools_raw.jsonl`.
EDAM ontology: `/home/jenifer/github/research_software_classification_attributes/data/raw/edam/EDAM.owl` with SHA256 `3da855ccb0f4b021477cb12bfd7949726e21d2376e7a2bbffb5666a984da6250`.

## Record Counts

| source | count_type | count |
| --- | --- | --- |
| papers_with_code | source_records | 573165 |
| papers_with_code | expanded_observations | 573165 |
| papers_with_code | labelled_records | 452486 |
| papers_with_code | github_backed_observations | 167690 |
| papers_with_code | retained_master_records | 146034 |
| papers_with_code | level1_records | 42692 |
| papers_with_code | level2_records | 141442 |
| papers_with_code | unique_normalized_repositories_observed | 150017 |
| papers_with_code | unique_dois_observed | 2269 |
| papers_with_code | unique_normalized_names_observed | 139571 |
| papers_with_code | source_records_by_repository_count | 405475 |
| papers_with_code | source_records_by_repository_count | 142583 |
| papers_with_code | source_records_by_repository_count | 15996 |
| papers_with_code | source_records_by_repository_count | 4053 |
| papers_with_code | source_records_by_repository_count | 1742 |
| papers_with_code | source_records_by_repository_count | 866 |
| papers_with_code | source_records_by_repository_count | 519 |
| papers_with_code | source_records_by_repository_count | 351 |
| papers_with_code | source_records_by_repository_count | 248 |
| papers_with_code | source_records_by_repository_count | 200 |
| papers_with_code | source_records_by_repository_count | 140 |
| papers_with_code | source_records_by_repository_count | 112 |
| papers_with_code | source_records_by_repository_count | 92 |
| papers_with_code | source_records_by_repository_count | 78 |
| papers_with_code | source_records_by_repository_count | 60 |
| papers_with_code | source_records_by_repository_count | 39 |
| papers_with_code | source_records_by_repository_count | 49 |
| papers_with_code | source_records_by_repository_count | 36 |
| papers_with_code | source_records_by_repository_count | 50 |
| papers_with_code | source_records_by_repository_count | 34 |
| papers_with_code | source_records_by_repository_count | 33 |
| papers_with_code | source_records_by_repository_count | 28 |
| papers_with_code | source_records_by_repository_count | 22 |
| papers_with_code | source_records_by_repository_count | 18 |
| papers_with_code | source_records_by_repository_count | 24 |
| papers_with_code | source_records_by_repository_count | 20 |
| papers_with_code | source_records_by_repository_count | 19 |
| papers_with_code | source_records_by_repository_count | 8 |
| papers_with_code | source_records_by_repository_count | 17 |
| papers_with_code | source_records_by_repository_count | 9 |

## Filtering

| stage | source | input_records | output_records | added_by_expansion | removed_records | removal_reason |
| --- | --- | --- | --- | --- | --- | --- |
| source_to_observation_expansion | papers_with_code | 573165 | 573165 | 0 | 0 | not_applicable |
| labelled_record_filter | papers_with_code | 573165 | 452486 | 0 | 120679 | missing_all_target_labels |
| github_backed_canonical_filter | papers_with_code | 452486 | 146034 | 0 | 306452 | missing_github_repository |
| level1_high_level_view_filter | papers_with_code | 146034 | 42692 | 0 | 103342 | missing_target_labels_for_level |
| level2_fine_grained_view_filter | papers_with_code | 146034 | 141442 | 0 | 4592 | missing_target_labels_for_level |
| source_to_observation_expansion | bio.tools | 33084 | 36417 | 3333 | 0 | not_applicable |
| labelled_record_filter | bio.tools | 36417 | 36417 | 0 | 0 | none |
| github_backed_canonical_filter | bio.tools | 36417 | 15294 | 0 | 21123 | missing_github_repository |
| level1_high_level_view_filter | bio.tools | 15294 | 14935 | 0 | 359 | missing_target_labels_for_level |
| level2_fine_grained_view_filter | bio.tools | 15294 | 15294 | 0 | 0 | none |

## Cohort Counts

| source | cohort | count | denominator | denominator_count | proportion_of_denominator | definition |
| --- | --- | --- | --- | --- | --- | --- |
| papers_with_code | source_universe | 573165 | None | None | None | Frozen source records before DOI expansion or filtering. |
| papers_with_code | expanded_source_observations | 573165 | source_universe | 573165 | 1.0 | Source observations after source-specific expansion, including bio.tools DOI expansion. |
| papers_with_code | labelled_records | 452486 | expanded_source_observations | 573165 | 0.78945155 | Expanded observations with at least one Level 1 or Level 2 target label, before the GitHub filter. |
| papers_with_code | github_backed_observations | 167690 | expanded_source_observations | 573165 | 0.29256846 | Expanded observations with a normalized GitHub repository URL, before the target-label filter. |
| papers_with_code | github_backed_research_software_analysis_cohort | 146034 | labelled_records | 452486 | 0.32273706 | Retained canonical cohort requiring both a normalized GitHub repository and at least one target label. |
| papers_with_code | level1_cohort | 42692 | github_backed_research_software_analysis_cohort | 146034 | 0.29234288 | Retained records with at least one Level 1 target label. |
| papers_with_code | level2_cohort | 141442 | github_backed_research_software_analysis_cohort | 146034 | 0.96855527 | Retained records with at least one Level 2 target label. |
| papers_with_code | publication_title_available_cohort | 146034 | github_backed_research_software_analysis_cohort | 146034 | 1.0 | Retained records with a publication title. |
| papers_with_code | publication_abstract_available_cohort | 145693 | github_backed_research_software_analysis_cohort | 146034 | 0.99766493 | Retained records with a publication abstract. |
| papers_with_code | readme_available_cohort | 46915 | github_backed_research_software_analysis_cohort | 146034 | 0.3212608 | Retained records with saved README content. |
| papers_with_code | somef_description_available_cohort | 40772 | github_backed_research_software_analysis_cohort | 146034 | 0.27919526 | Retained records with a SoMEF-derived description. |
| bio.tools | source_universe | 33084 | None | None | None | Frozen source records before DOI expansion or filtering. |
| bio.tools | expanded_source_observations | 36417 | source_universe | 33084 | 1.10074356 | Source observations after source-specific expansion, including bio.tools DOI expansion. |
| bio.tools | labelled_records | 36417 | expanded_source_observations | 36417 | 1.0 | Expanded observations with at least one Level 1 or Level 2 target label, before the GitHub filter. |
| bio.tools | github_backed_observations | 15294 | expanded_source_observations | 36417 | 0.4199687 | Expanded observations with a normalized GitHub repository URL, before the target-label filter. |
| bio.tools | github_backed_research_software_analysis_cohort | 15294 | labelled_records | 36417 | 0.4199687 | Retained canonical cohort requiring both a normalized GitHub repository and at least one target label. |
| bio.tools | level1_cohort | 14935 | github_backed_research_software_analysis_cohort | 15294 | 0.97652674 | Retained records with at least one Level 1 target label. |
| bio.tools | level2_cohort | 15294 | github_backed_research_software_analysis_cohort | 15294 | 1.0 | Retained records with at least one Level 2 target label. |
| bio.tools | publication_title_available_cohort | 14221 | github_backed_research_software_analysis_cohort | 15294 | 0.92984177 | Retained records with a publication title. |
| bio.tools | publication_abstract_available_cohort | 13159 | github_backed_research_software_analysis_cohort | 15294 | 0.86040277 | Retained records with a publication abstract. |
| bio.tools | readme_available_cohort | 13570 | github_backed_research_software_analysis_cohort | 15294 | 0.88727606 | Retained records with saved README content. |
| bio.tools | somef_description_available_cohort | 12349 | github_backed_research_software_analysis_cohort | 15294 | 0.80744083 | Retained records with a SoMEF-derived description. |

## Duplicates And Cross-Source Overlap

Duplicate and overlap evidence is written to machine-readable tables. No
within-source or cross-source duplicates are removed automatically.

## Missingness

Missingness is documented in `reports/MISSING_DATA_AUDIT.md` and
`reports/tables/missing_data_by_source.csv`.

## Enrichment Failures

Saved OpenAlex, README/GitHub, and SoMEF artifacts are audited without
recollection.

## PwC Hierarchy

PwC area-task relationships are reconstructed from co-occurrence in the frozen
source data. They are not invented when ambiguous.

## EDAM Hierarchy

EDAM mappings preserve multiple high-level ancestors when the ontology DAG
supports them.

## Label Granularity

| source | level | records | unique_labels | total_label_assignments | mean_labels_per_record | median_labels_per_record | single_label_records | multi_label_records | proportion_multi_label | minimum_support | maximum_support | median_support | mean_support | largest_class_proportion | rare_label_threshold | rare_label_count | rare_assignment_proportion | imbalance_ratio_max_min |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| bio.tools | level1_high_level | 14935 | 12 | 31724 | 2.1241 | 2 | 3673 | 11262 | 0.754068 | 25 | 13871 | 1107.5 | 2643.6667 | 0.43724 | 5 | 0 | 0.0 | 554.84 |
| bio.tools | level2_fine_grained | 15294 | 444 | 54019 | 3.532 | 3.0 | 1677 | 13617 | 0.890349 | 1 | 2504 | 13.5 | 121.6644 | 0.046354 | 5 | 158 | 0.00522 | 2504.0 |
| papers_with_code | level1_high_level | 42692 | 6 | 48688 | 1.1404 | 1.0 | 37079 | 5613 | 0.131477 | 222 | 22149 | 3754.0 | 8114.6667 | 0.454917 | 5 | 0 | 0.0 | 99.7703 |
| papers_with_code | level2_fine_grained | 141442 | 4591 | 409187 | 2.893 | 2.0 | 37302 | 104140 | 0.736274 | 1 | 6968 | 7 | 89.1281 | 0.017029 | 5 | 1935 | 0.008874 | 6968.0 |

Level 1 is the primary hierarchy-aligned cross-source comparison. Level 2 is a
fine-grained source-specific analysis space; direct cross-source Level 2
comparability remains a scientific question, not an assumption.

## Leakage Risks

Target-derived fields are preserved but classified as unsafe predictors where
they determine the target.

Deterministic `software_group_id`, `repository_group_id`, and
`publication_group_id` fields are included for later group-aware splitting. The
group leakage audit is written to `reports/EXPERIMENT_GROUP_LEAKAGE_AUDIT.md`.

## Remaining Scientific Concerns

| concern | status |
| --- | --- |
| Confirm whether the canonical source-observation unit is acceptable for final experiments. | REQUIRES_REVIEW |
| Review bio.tools DOI expansion before treating expanded rows as independent observations. | REQUIRES_REVIEW |
| Review PwC task-to-area non-determinism before using hierarchical claims. | REQUIRES_REVIEW |
| Review EDAM multi-parent mappings because EDAM is a DAG, not a tree. | REQUIRES_REVIEW |
| Treat Level 2 PwC tasks and EDAM topics as source-specific unless later review justifies direct comparison. | REQUIRES_REVIEW |
