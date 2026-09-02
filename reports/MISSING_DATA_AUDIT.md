# Missing Data Audit

## Missingness By Source

Missingness is calculated on the retained canonical master records and split by
source. Reasons distinguish not-applicable fields, source absence, failed
enrichment, and empty-after-cleaning cases.

| source | field | total_records | present_records | missing_records | present_proportion | genuinely_absent_in_source | failed_enrichment | not_applicable | empty_after_cleaning | removed_invalid_value |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| bio.tools | software_name | 15294 | 15294 | 0 | 1.0 | 0 | 0 | 0 | 0 | 0 |
| bio.tools | software_description | 15294 | 15294 | 0 | 1.0 | 0 | 0 | 0 | 0 | 0 |
| bio.tools | paper_title | 15294 | 14221 | 1073 | 0.92984177 | 0 | 82 | 0 | 991 | 0 |
| bio.tools | paper_abstract | 15294 | 13159 | 2135 | 0.86040277 | 951 | 152 | 0 | 1032 | 0 |
| bio.tools | publication_identifier | 15294 | 14335 | 959 | 0.93729567 | 959 | 0 | 0 | 0 | 0 |
| bio.tools | publication_url | 15294 | 14262 | 1032 | 0.93252256 | 1032 | 0 | 0 | 0 | 0 |
| bio.tools | doi | 15294 | 14262 | 1032 | 0.93252256 | 1032 | 0 | 0 | 0 | 0 |
| bio.tools | repository_url | 15294 | 15294 | 0 | 1.0 | 0 | 0 | 0 | 0 | 0 |
| bio.tools | repository_title | 15294 | 15294 | 0 | 1.0 | 0 | 0 | 0 | 0 | 0 |
| bio.tools | repository_description | 15294 | 0 | 15294 | 0.0 | 0 | 15294 | 0 | 0 | 0 |
| bio.tools | repository_keywords | 15294 | 0 | 15294 | 0.0 | 0 | 15294 | 0 | 0 | 0 |
| bio.tools | readme_content | 15294 | 13570 | 1724 | 0.88727606 | 0 | 1724 | 0 | 0 | 0 |
| bio.tools | somef_description | 15294 | 12349 | 2945 | 0.80744083 | 0 | 2945 | 0 | 0 | 0 |
| bio.tools | somef_keywords | 15294 | 0 | 15294 | 0.0 | 0 | 15294 | 0 | 0 | 0 |
| bio.tools | high_level_labels | 15294 | 14935 | 359 | 0.97652674 | 0 | 0 | 0 | 359 | 0 |
| bio.tools | fine_grained_labels | 15294 | 15294 | 0 | 1.0 | 0 | 0 | 0 | 0 | 0 |
| bio.tools | pwc_area_labels | 15294 | 0 | 15294 | 0.0 | 0 | 0 | 15294 | 0 | 0 |
| bio.tools | pwc_task_labels | 15294 | 0 | 15294 | 0.0 | 0 | 0 | 15294 | 0 | 0 |
| bio.tools | edam_topic_labels | 15294 | 15294 | 0 | 1.0 | 0 | 0 | 0 | 0 | 0 |
| bio.tools | edam_topic_uris | 15294 | 15294 | 0 | 1.0 | 0 | 0 | 0 | 0 | 0 |
| bio.tools | edam_top_level_labels | 15294 | 14935 | 359 | 0.97652674 | 0 | 0 | 0 | 359 | 0 |
| bio.tools | edam_top_level_uris | 15294 | 14935 | 359 | 0.97652674 | 0 | 0 | 0 | 359 | 0 |
| papers_with_code | software_name | 146034 | 0 | 146034 | 0.0 | 0 | 0 | 146034 | 0 | 0 |
| papers_with_code | software_description | 146034 | 0 | 146034 | 0.0 | 0 | 0 | 146034 | 0 | 0 |
| papers_with_code | paper_title | 146034 | 146034 | 0 | 1.0 | 0 | 0 | 0 | 0 | 0 |
| papers_with_code | paper_abstract | 146034 | 145693 | 341 | 0.99766493 | 0 | 0 | 0 | 341 | 0 |
| papers_with_code | publication_identifier | 146034 | 137460 | 8574 | 0.94128765 | 8574 | 0 | 0 | 0 | 0 |
| papers_with_code | publication_url | 146034 | 146034 | 0 | 1.0 | 0 | 0 | 0 | 0 | 0 |
| papers_with_code | doi | 146034 | 1106 | 144928 | 0.00757358 | 144928 | 0 | 0 | 0 | 0 |
| papers_with_code | repository_url | 146034 | 146034 | 0 | 1.0 | 0 | 0 | 0 | 0 | 0 |
| papers_with_code | repository_title | 146034 | 146033 | 1 | 0.99999315 | 0 | 1 | 0 | 0 | 0 |
| papers_with_code | repository_description | 146034 | 0 | 146034 | 0.0 | 0 | 146034 | 0 | 0 | 0 |
| papers_with_code | repository_keywords | 146034 | 0 | 146034 | 0.0 | 0 | 146034 | 0 | 0 | 0 |
| papers_with_code | readme_content | 146034 | 46915 | 99119 | 0.3212608 | 0 | 99119 | 0 | 0 | 0 |
| papers_with_code | somef_description | 146034 | 40772 | 105262 | 0.27919526 | 0 | 105262 | 0 | 0 | 0 |
| papers_with_code | somef_keywords | 146034 | 0 | 146034 | 0.0 | 0 | 146034 | 0 | 0 | 0 |
| papers_with_code | high_level_labels | 146034 | 42692 | 103342 | 0.29234288 | 0 | 0 | 0 | 103342 | 0 |
| papers_with_code | fine_grained_labels | 146034 | 141442 | 4592 | 0.96855527 | 0 | 0 | 0 | 4592 | 0 |
| papers_with_code | pwc_area_labels | 146034 | 58353 | 87681 | 0.39958503 | 0 | 0 | 0 | 87681 | 0 |
| papers_with_code | pwc_task_labels | 146034 | 141442 | 4592 | 0.96855527 | 0 | 0 | 0 | 4592 | 0 |
| papers_with_code | edam_topic_labels | 146034 | 0 | 146034 | 0.0 | 0 | 0 | 146034 | 0 | 0 |
| papers_with_code | edam_topic_uris | 146034 | 0 | 146034 | 0.0 | 0 | 0 | 146034 | 0 | 0 |
| papers_with_code | edam_top_level_labels | 146034 | 0 | 146034 | 0.0 | 0 | 0 | 146034 | 0 | 0 |
| papers_with_code | edam_top_level_uris | 146034 | 0 | 146034 | 0.0 | 0 | 0 | 146034 | 0 | 0 |
