# Experiment Group Leakage Audit

## Grouping Logic

- `repository_group_id`: SHA-256 identifier based on the normalized GitHub repository URL.
- `publication_group_id`: SHA-256 identifier based on normalized DOI when available; otherwise exact publication URL, source publication identifier, or exact-normalized title.
- `software_group_id`: for bio.tools, SHA-256 identifier based on `biotools_id`, so DOI-expanded rows from one tool share a software group; for PwC, SHA-256 identifier based on normalized repository identity when available, with source item fallback only for non-GitHub intermediate observations.

No fuzzy software/entity resolution is applied.

## Retained-Cohort Group Leakage Risk

| source | group_scope | total_retained_records | unique_groups | groups_containing_more_than_one_record | records_belonging_to_repeated_groups | largest_group_size | records_that_could_leak_under_naive_row_split | proportion_that_could_leak_under_naive_row_split |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| papers_with_code | software_group_id | 146034 | 131268 | 9659 | 24425 | 189 | 24425 | 0.16725557 |
| papers_with_code | repository_group_id | 146034 | 131268 | 9659 | 24425 | 189 | 24425 | 0.16725557 |
| papers_with_code | publication_group_id | 146034 | 146033 | 1 | 2 | 2 | 2 | 1.37e-05 |
| papers_with_code | any_group_id | 146034 | None | 19319 | 24425 | 189 | 24425 | 0.16725557 |
| bio.tools | software_group_id | 15294 | 14523 | 555 | 1326 | 12 | 1326 | 0.08670067 |
| bio.tools | repository_group_id | 15294 | 14256 | 669 | 1707 | 44 | 1707 | 0.1116124 |
| bio.tools | publication_group_id | 15294 | 13956 | 141 | 520 | 47 | 520 | 0.03400026 |
| bio.tools | any_group_id | 15294 | None | 1365 | 1933 | 47 | 1933 | 0.12638943 |

## Exact Cross-Source Overlap Counts

Counts are computed on retained records only.

| key_type | overlapping_keys | papers_with_code_records | biotools_records | total_records |
| --- | --- | --- | --- | --- |
| normalized_repository_url | 261 | 308 | 275 | 583 |
| doi | 10 | 10 | 10 | 20 |
