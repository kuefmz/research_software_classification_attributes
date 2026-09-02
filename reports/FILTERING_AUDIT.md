# Filtering Audit

## Filters Applied In The Candidate Master Build

The candidate master build applies only two record-level filters:

1. require a normalized GitHub repository URL;
2. require at least one target label at either Level 1 or Level 2.

It does not require a DOI for bio.tools. That older asymmetric rule is reported
as a scientific concern because it can bias bio.tools toward tools with formal
publication metadata.

## Accounting Table

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

## Source-Specific Label Cleanup

PwC `General` broad labels are removed from Level 1 targets but preserved in
`pwc_area_labels` and `raw_source_labels`.

- PwC records containing `General`: 114234
- PwC `General` assignments: 114234

## Bias Notes

The GitHub requirement is applied to both sources, but its impact is not
necessarily symmetric: PwC is paper-centered and bio.tools is software-centered.
Missing publication metadata is retained as missingness rather than becoming a
master-dataset exclusion.
