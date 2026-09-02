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

## Explicit Cohorts

The retained master is a GitHub-backed Research Software analysis cohort: it
requires a normalized GitHub repository and at least one Level 1 or Level 2
target label. It is not the complete Papers with Code or bio.tools population.

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
