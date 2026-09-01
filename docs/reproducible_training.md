# Reproducible Training Protocol

The protocol uses fixed train/test splits, deterministic classical classifiers,
frozen pretrained feature extraction, and optional local instruction-tuned
prompting. Transformer parameters are never updated.

## Training Script

Run the final paper-style local experiments with:

```bash
poetry run python scripts/run_final_results.py --models local_all --folds 3 --include-heavy-skipped
```

To include local LLM prompting, first choose the exact local model identifier and
runtime command:

```bash
poetry run python scripts/run_final_results.py --models all --folds 3 --include-heavy-skipped --enable-local-llm --local-llm-model XXX_LOCAL_LLM_MODEL --local-llm-command "YOUR_LOCAL_RUNTIME_COMMAND" --append-results
```

The local runtime must run on the same machine, read prompts from stdin, and
return structured JSON. No data is transmitted to an external commercial API.

## Model Groups

`--models simple` runs the sparse lexical baselines:

- `tfidf_logistic_regression`
- `tfidf_linear_svm`
- `tfidf_random_forest`
- `tfidf_xgboost`
- `tfidf_hard_voting`

`--models bert` runs frozen encoder pipelines. Text is embedded once and a
lightweight downstream classifier is trained on the embeddings:

- `modernbert_embedding_logistic_regression`
- `modernbert_embedding_random_forest`
- `scibert_embedding_logistic_regression`
- `scibert_embedding_random_forest`
- `deberta_v3_embedding_logistic_regression`
- `deberta_v3_embedding_random_forest`
- `roberta_embedding_logistic_regression`
- `roberta_embedding_random_forest`

`--models local_llm` runs:

- `local_llm_zero_shot`
- `local_llm_one_shot`
- `local_llm_few_shot`

Aliases:

- `simple` or `classical`: TF-IDF baselines only.
- `bert`: frozen BERT-family embedding pipelines only.
- `local_all`: simple plus frozen BERT-family pipelines.
- `local_llm` or `prompting`: local instruction-tuned prompting only.
- `all`: simple, frozen BERT-family, and local prompting pipelines.

## Predictor Fields

Attribute sets are defined in `scripts/run_final_results.py` and `src/config.py`.
The target field is `labels`. The runner excludes leakage-prone fields from
predictor text: `labels`, `tasks`, `methods`, and `secondary_labels`.

The main combined feature group is `all_non_target_textual_metadata`, not the
older unsafe all-metadata group.

## Reproducibility Controls

The runner writes deterministic train/test splits to `final_results/splits/` and
uses `RANDOM_SEED = 42`. The same split is reused across every attribute set and
model for a dataset.

The run configuration is saved to
`final_results/reports/run_configuration.json`, including:

- command-line settings
- package versions
- selected models
- attribute definitions and excluded leakage fields
- final dataset SHA-256 hashes
- frozen transformer model IDs
- embedding pooling method and cache metadata
- local LLM model identifier, prompt-template hash, retry settings, and whether
  a local command was configured
- hardware and platform information

Frozen transformer embeddings are cached in `final_results/embeddings/` as
`.npz` files with JSON metadata. The metadata records the Hugging Face model ID,
tokenizer max length, pooling method, batch size, device, package versions,
random seed, and SHA-256 hash of the exact input texts.

Local LLM responses are cached in `final_results/local_llm_cache/`. Full prompt
and response attempts are saved in `final_results/local_llm_conversations/`.
Predictions include prompt hashes, cache keys, parse attempts, invalid-response
counts, and conversation paths.

## Output Files

- `final_results/tables/classification_results.csv`: all split-level metrics.
- `final_results/tables/cv_summary.csv`: fold means and standard deviations when `--folds` is greater than 1.
- `final_results/tables/per_class_results.csv`: precision, recall, F1, and support by label.
- `final_results/tables/model_metadata.csv`: model families, encoder IDs, classifiers, and local-runtime flags.
- `final_results/tables/skipped_experiments.csv`: unavailable or not-yet-configured experiments.
- `final_results/predictions/predictions.jsonl`: train/test predictions.
- `final_results/reports/final_analysis_report.md`: human-readable summary.
- `final_results/reports/run_configuration.json`: reproducibility manifest.

## Practical Runs

Smoke test one dataset and one attribute group:

```bash
poetry run python scripts/run_final_results.py --skip-dataset-build --datasets pwc_single_only --attributes abstract_only --models tfidf_logistic_regression,tfidf_random_forest --smoke-test-records 10
```

Smoke test every configured local pipeline:

```bash
make training-smoke-all
```

Run all local non-updating models:

```bash
poetry run python scripts/run_final_results.py --models local_all --folds 3 --include-heavy-skipped
```

Run from local Hugging Face caches only:

```bash
poetry run python scripts/run_final_results.py --models local_all --folds 3 --offline-models-only
```
