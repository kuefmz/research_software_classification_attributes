# Dataset Scientific Validation

## Dataset Identity

The build creates a candidate canonical master dataset plus Level 1 and Level 2
analysis-ready views from frozen local inputs. It is not a final immutable
release until human review approves the scientific decisions.

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
| papers_with_code | source_records_by_repository_count | 14 |
| papers_with_code | source_records_by_repository_count | 10 |

## Filtering

| stage | source | input_records | output_records | added_by_expansion | removed_records | removal_reason |
| --- | --- | --- | --- | --- | --- | --- |
| source_to_observation_expansion | papers_with_code | 573165 | 573165 | 0 | 0 | not_applicable |
| canonical_master_filter | papers_with_code | 573165 | 146034 | 0 | 405475 | missing_github_repository |
| canonical_master_filter | papers_with_code | 573165 | 146034 | 0 | 21656 | missing_all_target_labels |
| level1_high_level_view_filter | papers_with_code | 146034 | 42692 | 0 | 103342 | missing_target_labels_for_level |
| level2_fine_grained_view_filter | papers_with_code | 146034 | 141442 | 0 | 4592 | missing_target_labels_for_level |
| source_to_observation_expansion | bio.tools | 33084 | 36417 | 3333 | 0 | not_applicable |
| canonical_master_filter | bio.tools | 36417 | 15294 | 0 | 21123 | missing_github_repository |
| level1_high_level_view_filter | bio.tools | 15294 | 14935 | 0 | 359 | missing_target_labels_for_level |
| level2_fine_grained_view_filter | bio.tools | 15294 | 15294 | 0 | 0 | none |

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
| bio.tools | level1_high_level | 15294 | 12 | 31724 | 2.0743 | 2.0 | 3673 | 11262 | 0.736367 | 25 | 13871 | 1107.5 | 2643.6667 | 0.43724 | 5 | 0 | 0.0 | 554.84 |
| bio.tools | level2_fine_grained | 15294 | 447 | 54019 | 3.532 | 3.0 | 1677 | 13617 | 0.890349 | 1 | 2504 | 13 | 120.8479 | 0.046354 | 5 | 163 | 0.005165 | 2504.0 |
| papers_with_code | level1_high_level | 146034 | 6 | 48688 | 0.3334 | 0.0 | 37079 | 5613 | 0.038436 | 222 | 22149 | 3754.0 | 8114.6667 | 0.454917 | 5 | 0 | 0.0 | 99.7703 |
| papers_with_code | level2_fine_grained | 146034 | 4591 | 409187 | 2.802 | 2.0 | 37302 | 104140 | 0.713122 | 1 | 6968 | 7 | 89.1281 | 0.017029 | 5 | 1935 | 0.008874 | 6968.0 |

## Leakage Risks

Target-derived fields are preserved but classified as unsafe predictors where
they determine the target.

## Remaining Scientific Concerns

| concern | status |
| --- | --- |
| Confirm whether the canonical source-observation unit is acceptable for final experiments. | REQUIRES_REVIEW |
| Review bio.tools DOI expansion before treating expanded rows as independent observations. | REQUIRES_REVIEW |
| Review PwC task-to-area non-determinism before using hierarchical claims. | REQUIRES_REVIEW |
| Review EDAM multi-parent mappings because EDAM is a DAG, not a tree. | REQUIRES_REVIEW |
| Confirm that Level 2 PwC tasks and EDAM topics are comparable enough for the intended analysis. | REQUIRES_REVIEW |
