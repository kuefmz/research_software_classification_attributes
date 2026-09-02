# Target Leakage Audit

## Field Classification

Target-derived fields are preserved for provenance, but they must not be used
as predictors when they determine the target level.

| field | classification | rationale |
| --- | --- | --- |
| source | SOURCE_IDENTIFIER | Stratification/provenance only, not a predictor. |
| source_item_id | SOURCE_IDENTIFIER | Stable source identifier. |
| canonical_record_id | SOURCE_IDENTIFIER | Deterministic row identifier. |
| software_group_id | SOURCE_IDENTIFIER | Deterministic group identifier for leakage-safe splitting. |
| repository_group_id | SOURCE_IDENTIFIER | Deterministic repository group identifier for leakage-safe splitting. |
| publication_group_id | SOURCE_IDENTIFIER | Deterministic publication group identifier for leakage-safe splitting. |
| repository_url | SOURCE_IDENTIFIER | Identifier/provenance, not semantic predictor. |
| repository_url_normalized | SOURCE_IDENTIFIER | Identifier/provenance, not semantic predictor. |
| publication_identifier | SOURCE_IDENTIFIER | Identifier/provenance, not semantic predictor. |
| doi | SOURCE_IDENTIFIER | Identifier/provenance, not semantic predictor. |
| paper_title | SAFE_METADATA | Publication text; safe unless target labels are embedded in title text by source convention. |
| paper_abstract | SAFE_METADATA | Publication text; safe textual metadata. |
| software_name | SAFE_METADATA | Name can contain domain hints; allowed but should be reported separately. |
| software_description | SAFE_METADATA | Source-provided software description. |
| repository_title | SAFE_METADATA | Repository text metadata. |
| repository_description | SAFE_METADATA | Repository text metadata. |
| repository_keywords | SAFE_METADATA | Repository topics may be user labels; inspect in sensitivity analyses. |
| readme_content | SAFE_METADATA | README text metadata. |
| somef_description | SAFE_METADATA | Description extracted from README, not source target hierarchy. |
| somef_keywords | SAFE_METADATA | README-derived keywords; audit because extraction can echo headings. |
| high_level_labels | TARGET | Level 1 target. |
| fine_grained_labels | TARGET | Level 2 target. |
| raw_source_labels | TARGET_DERIVED | Preserved target provenance. |
| raw_source_label_ids | TARGET_DERIVED | Preserved target provenance. |
| pwc_area_labels | TARGET | PwC Level 1 target labels. |
| pwc_task_labels | TARGET | PwC Level 2 target labels and leakage for PwC Level 1. |
| edam_topic_labels | TARGET | bio.tools Level 2 target labels and leakage for EDAM Level 1. |
| edam_topic_uris | TARGET | bio.tools Level 2 target identifiers. |
| edam_top_level_labels | TARGET | bio.tools Level 1 target labels. |
| edam_top_level_uris | TARGET | bio.tools Level 1 target identifiers. |
| pwc_method_labels | POTENTIAL_LEAKAGE | PwC method taxonomy is source classification metadata, not neutral text. |
| edam_operation_labels | POTENTIAL_LEAKAGE | EDAM operations are ontological annotations and may encode domain. |
| labels | TARGET_DERIVED | Legacy ambiguous target field, not safe as predictor. |
| secondary_labels | POTENTIAL_LEAKAGE | Legacy source classification metadata. |
| tasks | POTENTIAL_LEAKAGE | Legacy field is a Level 2 target for PwC and operation labels for bio.tools. |
| methods | POTENTIAL_LEAKAGE | Legacy source taxonomy metadata. |

## Critical Safeguards

- Do not use PwC task labels as predictors for PwC Level 1 classification.
- Do not use original EDAM topic labels or URIs as predictors for EDAM Level 1 classification.
- Do not use legacy `labels`, `tasks`, `secondary_labels`, or `methods` as generic text predictors.
- Keep identifiers out of model text features.
