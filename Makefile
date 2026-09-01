.PHONY: analysis analysis-fast training-smoke training-smoke-all training-simple training-local-all training-local-all-resume training-all-local-llm training-overnight-local-llm

analysis:
	poetry run python scripts/run_full_analysis.py

analysis-fast:
	poetry run python scripts/run_full_analysis.py --skip-training

training-smoke:
	poetry run python scripts/run_final_results.py --skip-dataset-build --datasets pwc_single_only --attributes abstract_only --models tfidf_logistic_regression,tfidf_random_forest --smoke-test-records 10

training-smoke-all:
	poetry run python scripts/run_final_results.py --skip-dataset-build --datasets pwc_single_only --attributes abstract_only --models all --smoke-test-records 10 --embedding-max-length 64 --output-dir final_results_smoke_all_pipelines

training-simple:
	poetry run python scripts/run_final_results.py --models simple --include-heavy-skipped

training-local-all:
	poetry run python scripts/run_final_results.py --models local_all --folds 3 --include-heavy-skipped

training-local-all-resume:
	poetry run python scripts/run_final_results.py --models local_all --folds 3 --include-heavy-skipped --append-results --skip-existing-results

training-all-local-llm:
	poetry run python scripts/run_final_results.py --models all --folds 3 --include-heavy-skipped --enable-local-llm --local-llm-model XXX_LOCAL_LLM_MODEL --local-llm-command "YOUR_LOCAL_RUNTIME_COMMAND" --append-results

training-overnight-local-llm:
	poetry run python scripts/run_final_results.py --models all --folds 3 --include-heavy-skipped --enable-local-llm --local-llm-model XXX_LOCAL_LLM_MODEL --local-llm-command "YOUR_LOCAL_RUNTIME_COMMAND" --append-results
