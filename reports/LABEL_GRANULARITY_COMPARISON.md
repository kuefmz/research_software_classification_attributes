# Label Granularity Comparison

## Label-Space Comparison

The comparison is based on hierarchy role, multi-label behavior, support, and
imbalance. Similar label counts are not treated as evidence of comparability.

| source | level | records | unique_labels | total_label_assignments | mean_labels_per_record | median_labels_per_record | single_label_records | multi_label_records | proportion_multi_label | minimum_support | maximum_support | median_support | mean_support | largest_class_proportion | rare_label_threshold | rare_label_count | rare_assignment_proportion | imbalance_ratio_max_min |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| bio.tools | level1_high_level | 14935 | 12 | 31724 | 2.1241 | 2 | 3673 | 11262 | 0.754068 | 25 | 13871 | 1107.5 | 2643.6667 | 0.43724 | 5 | 0 | 0.0 | 554.84 |
| bio.tools | level2_fine_grained | 15294 | 444 | 54019 | 3.532 | 3.0 | 1677 | 13617 | 0.890349 | 1 | 2504 | 13.5 | 121.6644 | 0.046354 | 5 | 158 | 0.00522 | 2504.0 |
| papers_with_code | level1_high_level | 42692 | 6 | 48688 | 1.1404 | 1.0 | 37079 | 5613 | 0.131477 | 222 | 22149 | 3754.0 | 8114.6667 | 0.454917 | 5 | 0 | 0.0 | 99.7703 |
| papers_with_code | level2_fine_grained | 141442 | 4591 | 409187 | 2.893 | 2.0 | 37302 | 104140 | 0.736274 | 1 | 6968 | 7 | 89.1281 | 0.017029 | 5 | 1935 | 0.008874 | 6968.0 |

## Scientific Interpretation

Level 1 compares PwC broad collection areas with the highest meaningful EDAM
Topic categories below the generic Topic root. Level 1 is the primary
hierarchy-aligned cross-source comparison, subject to human review of the EDAM
DAG multi-parent cases.

Level 2 compares PwC tasks with original EDAM topics as fine-grained
source-specific analysis spaces. Direct cross-source Level 2 comparability
remains a scientific question, not an assumption: EDAM topics are ontology
concepts, while PwC tasks are task taxonomy entries.

PwC task-to-area relationships are empirical co-occurrences in the frozen
source data and are not assumed to be deterministic.
