# Final Datasets

This folder contains the three final datasets used for the final analysis.
They are built from `data/final_edam_top_level/combined_all_with_somef.jsonl`
and keep only the attributes used by the final metadata-comparison analysis.

## Files

- `final_single_label.jsonl`: records with exactly one target label.
- `final_multi_label_only.jsonl`: records with two or more target labels.
- `final_combined.jsonl`: all final labelled records.
- `dataset_overview.csv`: dataset-level counts.
- `label_distribution_by_source.csv`: label support by source.
- `attribute_coverage.csv`: text availability for each final attribute set.

The single-label file is used for single-only classification experiments. The
multi-label-only file is used for multi-only classification experiments. The
combined file is used for merged classification experiments where single-label
and multi-label records for the same source are evaluated together.

## Schema

Each JSONL row contains:

```text
source, item_id, software_name, software_description, paper_title,
paper_abstract, publication_url, repository_url, repository_title,
repository_description, repository_keywords, readme_content,
somef_description, tasks, methods, secondary_labels, labels, label,
label_count, is_single_label, is_multi_label
```

`labels` is always a list. `label` is filled only for records with exactly one
target label.

## Dataset Overview

| dataset | records | sources | papers_with_code_records | biotools_records | unique_labels_total | unique_papers_with_code_labels | unique_biotools_labels | records_with_readme | records_with_somef_description | records_with_title_or_abstract |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| final_single_label | 40330 | bio.tools, papers_with_code | 37058 | 3272 | 17 | 6 | 11 | 39080 | 34135 | 40305 |
| final_multi_label_only | 16489 | bio.tools, papers_with_code | 5611 | 10878 | 18 | 6 | 12 | 15813 | 14165 | 16438 |
| final_combined | 56819 | bio.tools, papers_with_code | 42669 | 14150 | 18 | 6 | 12 | 54893 | 48300 | 56743 |

## Label Distribution

### Papers with Code

| source | label | support | percent_of_source_assignments |
| --- | --- | --- | --- |
| papers_with_code | Computer Vision | 22138 | 45.49340347704575 |
| papers_with_code | Natural Language Processing | 16585 | 34.08203526365542 |
| papers_with_code | Graphs | 5220 | 10.72705601907032 |
| papers_with_code | Sequential | 2287 | 4.699765730960503 |
| papers_with_code | Reinforcement Learning | 2210 | 4.541531379721343 |
| papers_with_code | Audio | 222 | 0.4562081295466688 |

### bio.tools

| source | label | support | percent_of_source_assignments |
| --- | --- | --- | --- |
| bio.tools | Biosciences | 13234 | 43.45570368424509 |
| bio.tools | Data acquisition | 6801 | 22.332041767912266 |
| bio.tools | Computer science | 3176 | 10.428843501674658 |
| bio.tools | Data management | 1869 | 6.137124844027057 |
| bio.tools | Informatics | 1145 | 3.759768831680568 |
| bio.tools | Environmental sciences | 1096 | 3.5988704275300454 |
| bio.tools | Mathematics | 1016 | 3.33617915544756 |
| bio.tools | Chemistry | 756 | 2.482432521179484 |
| bio.tools | Experimental design and studies | 626 | 2.0555592040454456 |
| bio.tools | Literature and language | 456 | 1.497340250870165 |
| bio.tools | Physics | 258 | 0.8471793524660144 |
| bio.tools | Open science | 21 | 0.0689564589216523 |

## Attribute Coverage

| source | attribute_set | records_with_text | records | coverage_percent |
| --- | --- | --- | --- | --- |
| bio.tools | abstract_only | 13062 | 14150 | 92.31095406360424 |
| bio.tools | title_only | 14074 | 14150 | 99.46289752650176 |
| bio.tools | repository_title_keywords | 14150 | 14150 | 100.0 |
| bio.tools | abstract_readme_description | 14150 | 14150 | 100.0 |
| bio.tools | abstract_repository_title_keywords | 14150 | 14150 | 100.0 |
| bio.tools | all_publication_metadata | 14150 | 14150 | 100.0 |
| bio.tools | all_repository_metadata | 14150 | 14150 | 100.0 |
| bio.tools | all_available_metadata | 14150 | 14150 | 100.0 |
| papers_with_code | abstract_only | 42665 | 42669 | 99.99062551266728 |
| papers_with_code | title_only | 42669 | 42669 | 100.0 |
| papers_with_code | repository_title_keywords | 42669 | 42669 | 100.0 |
| papers_with_code | abstract_readme_description | 42669 | 42669 | 100.0 |
| papers_with_code | abstract_repository_title_keywords | 42669 | 42669 | 100.0 |
| papers_with_code | all_publication_metadata | 42669 | 42669 | 100.0 |
| papers_with_code | all_repository_metadata | 42669 | 42669 | 100.0 |
| papers_with_code | all_available_metadata | 42669 | 42669 | 100.0 |

## Attribute Sets Used In The Final Analysis

```json
{
  "abstract_only": [
    "paper_abstract"
  ],
  "title_only": [
    "paper_title"
  ],
  "repository_title_keywords": [
    "repository_title",
    "repository_keywords"
  ],
  "abstract_readme_description": [
    "paper_abstract",
    "readme_content",
    "software_description",
    "repository_description"
  ],
  "abstract_repository_title_keywords": [
    "paper_abstract",
    "repository_title",
    "repository_keywords"
  ],
  "all_publication_metadata": [
    "paper_title",
    "paper_abstract",
    "publication_url"
  ],
  "all_repository_metadata": [
    "repository_title",
    "repository_description",
    "repository_keywords",
    "readme_content",
    "somef_description"
  ],
  "all_available_metadata": [
    "paper_title",
    "paper_abstract",
    "software_name",
    "software_description",
    "repository_title",
    "repository_description",
    "repository_keywords",
    "readme_content",
    "somef_description",
    "tasks",
    "methods",
    "secondary_labels"
  ]
}
```

## Running The Final Analysis

From the repository root, run:

```bash
poetry run python scripts/run_final_results.py
```

This rebuilds the files in this folder and writes all result tables, figures,
predictions, logs, and reports to `final_results/`.
The analysis trains PwC and bio.tools separately across six datasets:
PwC single-only, PwC multi-only, PwC merged, bio.tools single-only,
bio.tools multi-only, and bio.tools merged.
