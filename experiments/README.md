# KAIS experiment runner

Notebook: `experiments/kais_experiments_colab.ipynb`

## Run

1. Open the notebook in Google Colab:
   https://colab.research.google.com/github/kuefmz/research_software_classification_attributes/blob/phd-colab-experiments-2026-09-01/experiments/kais_experiments_colab.ipynb
2. Runtime -> Change runtime type -> GPU.
3. Runtime -> Run all.
4. Approve the Google Drive mount when Colab asks.

No other manual configuration is required for the core runs.

## Drive outputs

The notebook writes to:

`MyDrive/phd_kais_experiments_2026_09_01/`

Key outputs:

- `results/dataset_inventory.csv`
- `results/pwc_attribute_coverage.csv`
- `results/single_label_available_case.csv`
- `results/single_label_per_class.csv`
- `results/single_label_matched_individual.csv`
- `results/single_label_attribute_combinations.csv`
- `results/multilabel_tfidf.csv`
- `results/sbert_matched_results.csv`
- `results/biotools_external_validation.csv`
- `results/llm_pilot_summary.csv` (GPU pilot)
- `results/MASTER_RESULTS.csv`
- `results/PAPER_TABLE.csv`
- `results/PAPER_TABLE.tex`

The Zenodo source artifact and cached embeddings are also stored under that Drive folder so completed work survives a Colab disconnect.

## Experiment policy

Core paper evidence runs before the LLM pilot. The notebook:
- fits TF-IDF within each training fold;
- reuses fixed 5-fold splits;
- reports macro/micro/weighted F1, standard deviation and 95% CI;
- retains single-label observations in the multi-label experiment;
- includes a matched-cohort comparison for fair attribute comparisons;
- explicitly tests publication + repository attribute combinations;
- tests classifier robustness with Logistic Regression, Linear SVM, Random Forest and XGBoost;
- uses Sentence-BERT `all-MiniLM-L6-v2`, matching the earlier experiment notebook;
- treats bio.tools as an external-validity dataset rather than claiming its EDAM taxonomy is identical to Papers with Code.
