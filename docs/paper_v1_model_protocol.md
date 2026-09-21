# Paper v1 model protocol

This document records the exact implementation details for the model families reported in the paper *A Comparative Analysis of Semantic Attributes for Research Software Classification*. It is intentionally more technical than the manuscript. The paper describes the scientific role of each model family; this file records concrete identifiers, revisions, hyperparameters, pooling choices, and training settings needed for reproducibility.

## Scope

The protocol applies to the final paper-v1 Level 1 experiments used for RQ4 and RQ5. The two source ecosystems are evaluated as separate source-specific multi-label tasks. The model protocol is applied only to validated final artifacts with exact provenance.

## Sparse lexical representation

TF-IDF uses:
- word unigrams and bigrams
- sublinear term frequency
- `min_df=2`
- maximum 50,000 features
- vocabulary and weights fit on training data only

Multi-label classification uses one-vs-rest decomposition.

### LinearSVC

Used as:
- the fixed classifier for RQ4 representation ablation
- the sparse discriminative baseline for RQ5

Estimator:

```python
LinearSVC(
    class_weight="balanced",
    random_state=42,
)
```

### Logistic Regression

Used as the sparse probabilistic linear baseline for RQ5.

Estimator:

```python
LogisticRegression(
    max_iter=2000,
    class_weight="balanced",
    solver="liblinear",
    random_state=42,
)
```

## Frozen dense encoders

The encoder is frozen and only the downstream one-vs-rest logistic-regression probe is fit on training embeddings.

### MiniLM

Model:
- `sentence-transformers/all-MiniLM-L6-v2`
- revision: `1110a243fdf4706b3f48f1d95db1a4f5529b4d41`

Representation:
- SentenceTransformer default pooling

Downstream classifier:
- one-vs-rest logistic-regression probe

Scientific role:
- general-purpose dense semantic representation

### SPECTER2

Model:
- `allenai/specter2_base`
- revision: `3447645e1def9117997203454fa4495937bfbd83`

Representation:
- CLS representation

Downstream classifier:
- the same one-vs-rest logistic-regression probe used for MiniLM

Scientific role:
- scientific-document-specific dense representation

The MiniLM/SPECTER2 comparison therefore changes the pretrained encoder while keeping the downstream classifier family fixed.

## SciBERT

Model:
- `allenai/scibert_scivocab_uncased`
- revision: `24f92d32b1bfb0bcaf9ab193ff3ad01e87732fc1`

Training:
- end-to-end fine-tuning
- source-specific multi-label classification head
- input representation: `Combined Safe`
- maximum sequence length: 512
- learning rate: `2e-5`
- maximum epochs: 3
- weight decay: `0.01`
- per-device batch size: 8
- gradient accumulation steps: 2
- mixed precision
- binary cross-entropy with logits
- validation-based early stopping
- early-stopping patience: 1

The final global decision threshold is selected on validation predictions and frozen before test evaluation.

## Controlled RQ5 representations

RQ5 uses the reduced representation set:
- `Publication`
- `Software/Repository`
- `Combined Safe`

This restriction is deliberate: RQ4 studies the effect of metadata representation with one fixed classifier, whereas RQ5 studies the effect of model family under a smaller controlled representation set.

## Leakage-sensitive metadata

GitHub Topics (`repository_keywords`) are excluded from all primary safe representations because they can directly express domain terminology proximal to the target labels.

If evaluated, `Combined Safe + GitHub Topics` is treated only as a leakage-sensitive sensitivity analysis and is not part of the primary model comparison.

## Threshold selection for multi-label sparse models

A single global decision threshold is selected using validation scores only.

Candidate thresholds:
- 41 equally spaced values between the 5th and 95th percentiles of validation scores
- plus `0.0`
- plus `0.5`

Selection:
1. maximize validation Macro-F1
2. tie-break using validation Micro-F1
3. final deterministic tie-break: smallest absolute threshold

The test partition is not used during threshold selection.

## Evaluation and uncertainty

Primary Level 1 metric:
- Macro-F1

Supporting metrics:
- Micro-F1
- Weighted-F1
- sample-averaged F1
- subset accuracy
- Hamming loss

Major within-source/task comparisons use dependency-component bootstrap uncertainty:
- 1,000 replicates
- 95% percentile confidence intervals
- identical component resamples for paired conditions
- paired comparisons only within the same source, task, and frozen partition

No paired Papers with Code versus bio.tools significance test is performed.

## Reproducibility principle

All learned preprocessing and model parameters are estimated without test information. Training-only fitting applies to:
- TF-IDF vocabulary and weights
- label binarization vocabulary
- downstream classifiers
- dense-encoder probes
- fine-tuned neural models

Validation is used only for pre-specified model or threshold decisions. Test evaluation is performed only after the configuration is frozen.
