# Unit Of Analysis Audit

## Recommendation

Use the canonical master row as a source observation with stable provenance, not
as a silently deduplicated software package. For PwC, one row represents one
PwC paper/source record with all known repository URLs preserved. For bio.tools,
one row represents one tool-publication observation when DOI information exists,
and one tool observation when it does not. This mismatch is scientifically
important and remains marked for human review before any final experiment.

## Core Counts

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

## Bio.tools DOI Expansion

bio.tools raw tool rows can expand when multiple DOI values are attached to one
software entry. Expanded rows preserve the same software metadata and differ by
publication identifier. This is evidence of a possible dependence structure,
not a deduplication instruction.

Publication expansion distribution:

| value | count |
| --- | --- |
| 1 | 31043 |
| 2 | 1240 |
| 3 | 585 |
| 4 | 120 |
| 5 | 35 |
| 6 | 23 |
| 7 | 15 |
| 9 | 7 |
| 10 | 4 |
| 8 | 4 |
| 14 | 3 |
| 12 | 3 |

## Repository Multiplicity

PwC records may reference zero, one, or multiple repositories. The canonical
record preserves the full normalized repository list and uses the first
normalized GitHub URL as the primary repository for model-ready views.

PwC repository count distribution:

| value | count |
| --- | --- |
| 0 | 405475 |
| 1 | 142583 |
| 2 | 15996 |
| 3 | 4053 |
| 4 | 1742 |
| 5 | 866 |
| 6 | 519 |
| 7 | 351 |
| 8 | 248 |
| 9 | 200 |
| 10 | 140 |
| 11 | 112 |
