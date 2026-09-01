# Current Paper Result Status

This note summarizes which result artifacts can currently support manuscript
claims.

## Verified Classification Results

The checked-in `final_results/tables/classification_results.csv` contains five
completed held-out test rows:

- Dataset: `pwc_single_only`
- Source: Papers with Code
- Label setting: single-label
- Attribute set: `abstract_only`
- Pipelines: TF-IDF logistic regression, LinearSVC, random forest, XGBoost, and
  hard voting

These rows are the only classification metrics reported as validated in the
current manuscript.

## Excluded Historical Results

Older tables under `results/` contain all-metadata rows generated before the
predictor leakage audit. They are not used as findings because historical
definitions included target-derived or target-adjacent fields.

## Pending Experiments

The next full run should use:

```bash
poetry run python scripts/run_final_results.py --models local_all --folds 3 --include-heavy-skipped
```

Prompting experiments require a selected local instruction-tuned model and a
runtime command that reads prompts from stdin and returns structured JSON.
