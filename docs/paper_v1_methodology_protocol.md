# Paper v1 methodology implementation protocol

This document records implementation-level details that support the Methodology section of the paper *A Comparative Analysis of Semantic Attributes for Research Software Classification*. The manuscript describes the scientific design, assumptions, comparisons, and evaluation logic. This file preserves concrete implementation choices needed for exact computational reproducibility.

For model-specific checkpoints and training hyperparameters, see [paper_v1_model_protocol.md](paper_v1_model_protocol.md).

## Frozen analytical cohorts

Final frozen master cohort:
- total: 160,976 observations
- Papers with Code: 146,034
- bio.tools: 14,942

Level 1 cohort:
- total: 57,627
- Papers with Code: 42,692
- bio.tools: 14,935

Level 2 cohort:
- total: 156,384
- Papers with Code: 141,442
- bio.tools: 14,942

## Semantic-dimension representation

The analytical crosswalk uses six dimensions:
1. software/repository identity
2. software description
3. publication metadata
4. research classification
5. function/operation
6. documentation/repository metadata

A dimension is marked as represented for an observation when at least one mapped field contains a usable value.

Native GitHub repository descriptions and SoMEF-derived descriptions remain separate fields in the frozen data.

GitHub Topics are stored as `repository_keywords`. They are treated as target-proximal and are excluded from primary safe predictor representations.

## Coverage and completeness implementation

For each source and semantic dimension, coverage is the proportion of source observations for which that dimension is represented.

Within-source completeness uses the source-specific set of structurally applicable descriptive dimensions.

Shared-dimension completeness uses only descriptive dimensions represented in both source schemas.

Repository-group sensitivity groups observations within source by normalized repository and aggregates metadata availability with logical OR.

## Level 1 task construction

Papers with Code:
- target: broad research-area labels

bio.tools:
- target: high-level EDAM Topics obtained by traversing the EDAM DAG to Topic concepts immediately below the generic Topic root
- all valid high-level parent paths are retained

The source-specific target vocabularies are not merged.

## Level 2 task construction

Papers with Code:
- target: task labels

bio.tools:
- target: detailed EDAM Topics

The task is flat multi-label classification.

Minimum training-support thresholds:
- 5
- 10
- 20

Eligibility is computed from training support only. The eligible vocabulary is frozen and applied unchanged to train, validation, and test. A record is removed from a threshold-specific view only if no eligible labels remain after filtering.

A training-eligible label remains in the evaluation universe even when it has zero positive examples in validation or test.

## Single-label sensitivity

The single-label sensitivity view retains only observations with exactly one Level 1 label.

These observations inherit the existing Level 1 dependency-aware partition. No new random split is created.

## Metadata representations

RQ4 evaluates the following pre-specified representations:
- publication title
- publication abstract
- title + abstract
- software/repository name
- software description
- README
- SoMEF description
- native GitHub repository description
- Publication aggregate
- Software/Repository aggregate
- Combined Safe

GitHub Topics (`repository_keywords`) are excluded from primary safe representations.

If evaluated, `Combined Safe + GitHub Topics` is treated only as a leakage-sensitive sensitivity analysis.

RQ5 uses the reduced controlled representation set:
- Publication
- Software/Repository
- Combined Safe

## Dependency-aware partitioning

Level 1 observations are grouped through connected components formed from:
- software-group identity
- repository-group identity
- publication-group identity

Each component is assigned wholly to one partition.

Target proportions:
- 70% train
- 15% validation
- 15% test

Random seed:
- 42

Validated final split:
- train: 40,339
- validation: 8,644
- test: 8,644
- dependency components: 53,633

Leakage audit:
- no software-group identifier crosses partitions
- no repository-group identifier crosses partitions
- no publication-group identifier crosses partitions

The same assignment is reused across directly comparable RQ4/RQ5 conditions and inherited by the single-label sensitivity analysis.

## Training-only fitting

All learned preprocessing and model parameters are fit without test information.

Training-only fitting includes:
- TF-IDF vocabulary
- TF-IDF weights
- label binarization vocabulary
- sparse classifiers
- downstream embedding probes
- fine-tuned neural models

Validation is used only for pre-specified configuration and threshold decisions. The test split is used only after the corresponding configuration has been frozen.

Predictor construction excludes:
- target labels
- deterministic target derivatives
- grouping identifiers
- target-proximal annotations from primary safe representations

## Global threshold selection

For multi-label TF-IDF models, one global decision threshold is selected using validation scores only.

Candidate set:
- 41 equally spaced values between the 5th and 95th percentiles of the validation-score distribution
- `0.0`
- `0.5`

Selection:
1. maximize validation Macro-F1
2. tie-break with validation Micro-F1
3. final deterministic tie-break: smallest absolute threshold

LinearSVC uses decision-function scores. Logistic regression uses predicted probabilities.

The selected threshold is frozen before test evaluation.

## Level 2 Macro-F1 implementation

Macro-F1 is calculated over the full training-eligible label vocabulary.

Implementation uses `zero_division=0`.

Thus a training-eligible label with no positive examples in validation or test remains in the evaluation matrix and contributes zero where precision or recall is undefined rather than being removed from the macro average.

## Bootstrap uncertainty

Major within-source/task representation and model comparisons use dependency-component bootstrap resampling.

Protocol:
- resampling unit: dependency component
- replicates: 1,000
- interval: 95% percentile confidence interval
- paired conditions use identical component resamples

Paired comparisons are only defined within the same:
- source
- task
- frozen partition

No paired Papers with Code versus bio.tools significance test is performed.

## Error-analysis outputs

Diagnostic outputs include:
- class-level precision
- class-level recall
- class-level F1
- class support
- support-performance relationships
- false-positive / false-negative patterns
- label-cardinality error for multi-label tasks
- confusion patterns for the single-label sensitivity analysis

These diagnostics are not used to choose a model after observing the test set.

## Reproducibility records

The experiment provenance should retain:
- dataset identity / hashes
- split identity
- random seed
- package versions
- exact model identifiers and revisions
- preprocessing configuration
- representation definitions
- threshold decisions
- evaluation configuration
- output artifact identity

Model-specific details are documented in [paper_v1_model_protocol.md](paper_v1_model_protocol.md).
