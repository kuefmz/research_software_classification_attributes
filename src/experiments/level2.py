from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any, Mapping, Sequence
import json
import os
import time
import warnings

import numpy as np
from sklearn.exceptions import ConvergenceWarning
from sklearn.svm import LinearSVC

PARTITIONS = ("train", "validation", "test")


def _source_rows(rows: Sequence[Mapping[str, Any]], source: str) -> list[Mapping[str, Any]]:
    return [r for r in rows if r.get("source") == source and r.get("target_labels")]


def _filtered_partition_summary(
    rows: Sequence[Mapping[str, Any]],
    eligible_labels: set[str],
) -> dict[str, Any]:
    retained_records = 0
    label_assignments = 0
    label_support = {label: 0 for label in sorted(eligible_labels)}
    for row in rows:
        retained = [label for label in (row.get("target_labels") or []) if label in eligible_labels]
        if not retained:
            continue
        retained_records += 1
        label_assignments += len(retained)
        for label in retained:
            label_support[label] += 1
    return {
        "retained_records": retained_records,
        "label_assignments": label_assignments,
        "label_support": label_support,
    }


def support_threshold_analysis(
    *,
    train_rows: Sequence[Mapping[str, Any]],
    validation_rows: Sequence[Mapping[str, Any]],
    test_rows: Sequence[Mapping[str, Any]],
    source: str,
    thresholds: Sequence[int] = (5, 10, 20),
) -> list[dict[str, Any]]:
    """Summarize Level-2 support sensitivity using training-derived eligibility only.

    Label eligibility is computed exactly once from the training partition for
    each threshold. The resulting label set is then applied unchanged to
    training, validation, and test rows. Validation/test support can therefore
    neither promote nor demote a label.
    """
    parts = {
        "train": _source_rows(train_rows, source),
        "validation": _source_rows(validation_rows, source),
        "test": _source_rows(test_rows, source),
    }
    training_support = Counter(
        label
        for row in parts["train"]
        for label in (row.get("target_labels") or [])
    )

    results: list[dict[str, Any]] = []
    for threshold in thresholds:
        if threshold <= 0:
            raise ValueError("Support thresholds must be positive integers")
        eligible_labels = {
            label for label, count in training_support.items() if count >= threshold
        }
        partition_summary = {
            partition: _filtered_partition_summary(parts[partition], eligible_labels)
            for partition in PARTITIONS
        }
        results.append(
            {
                "source": source,
                "threshold": int(threshold),
                "eligible_label_count": len(eligible_labels),
                "eligible_labels": sorted(eligible_labels),
                "training_support": {
                    label: int(training_support[label])
                    for label in sorted(eligible_labels)
                },
                "train_retained_records": partition_summary["train"]["retained_records"],
                "validation_retained_records": partition_summary["validation"]["retained_records"],
                "test_retained_records": partition_summary["test"]["retained_records"],
                "train_label_assignments": partition_summary["train"]["label_assignments"],
                "validation_label_assignments": partition_summary["validation"]["label_assignments"],
                "test_label_assignments": partition_summary["test"]["label_assignments"],
                "partition_label_support": {
                    partition: partition_summary[partition]["label_support"]
                    for partition in PARTITIONS
                },
            }
        )
    return results


def _atomic_json(path: Path, payload: Mapping[str, Any]) -> None:
    """Write a JSON checkpoint without leaving a partially-written final file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def _binary_column(matrix: Any, index: int) -> np.ndarray:
    """Return one binary target column as a compact 1-D int8 array."""
    column = matrix[:, index]
    if hasattr(column, "toarray"):
        column = column.toarray()
    return np.asarray(column).reshape(-1).astype(np.int8, copy=False)


def _checkpoint_path(checkpoint_dir: Path, index: int) -> Path:
    return checkpoint_dir / "label_scores" / f"label_{index:05d}.npz"


def _load_label_checkpoint(
    path: Path,
    *,
    label: str,
    label_index: int,
    validation_rows: int,
    test_rows: int,
) -> dict[str, Any] | None:
    """Load a per-label score checkpoint only when all identity/shape gates pass."""
    if not path.exists() or path.stat().st_size == 0:
        return None
    try:
        with np.load(path, allow_pickle=False) as data:
            saved_label = str(np.asarray(data["label"]).item())
            saved_index = int(np.asarray(data["label_index"]).item())
            validation_scores = np.asarray(data["validation_scores"], dtype=np.float32)
            test_scores = np.asarray(data["test_scores"], dtype=np.float32)
            n_iter = int(np.asarray(data["n_iter"]).item())
            converged = bool(np.asarray(data["converged"]).item())
            elapsed_seconds = float(np.asarray(data["elapsed_seconds"]).item())
            train_positive = int(np.asarray(data["train_positive"]).item())
    except Exception:
        return None
    if saved_label != label or saved_index != label_index:
        return None
    if validation_scores.shape != (validation_rows,) or test_scores.shape != (test_rows,):
        return None
    if not np.isfinite(validation_scores).all() or not np.isfinite(test_scores).all():
        return None
    return {
        "validation_scores": validation_scores,
        "test_scores": test_scores,
        "n_iter": n_iter,
        "converged": converged,
        "elapsed_seconds": elapsed_seconds,
        "train_positive": train_positive,
    }


def _save_label_checkpoint(
    path: Path,
    *,
    label: str,
    label_index: int,
    validation_scores: np.ndarray,
    test_scores: np.ndarray,
    n_iter: int,
    converged: bool,
    elapsed_seconds: float,
    train_positive: int,
) -> None:
    """Atomically persist one completed classifier's validation/test scores."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    with tmp.open("wb") as handle:
        np.savez_compressed(
            handle,
            label=np.asarray(label),
            label_index=np.asarray(label_index, dtype=np.int32),
            validation_scores=np.asarray(validation_scores, dtype=np.float32),
            test_scores=np.asarray(test_scores, dtype=np.float32),
            n_iter=np.asarray(n_iter, dtype=np.int32),
            converged=np.asarray(converged, dtype=np.bool_),
            elapsed_seconds=np.asarray(elapsed_seconds, dtype=np.float64),
            train_positive=np.asarray(train_positive, dtype=np.int32),
        )
    os.replace(tmp, path)


def resumable_ovr_linearsvc_scores(
    *,
    x_train: Any,
    y_train: Any,
    x_validation: Any,
    x_test: Any,
    labels: Sequence[str],
    checkpoint_dir: str | Path,
    random_state: int = 42,
    class_weight: str | Mapping[int, float] | None = "balanced",
    max_iter: int = 5000,
    tol: float = 1e-4,
    progress_every: int = 1,
) -> tuple[np.ndarray, np.ndarray, list[dict[str, Any]]]:
    """Fit/reuse one-vs-rest LinearSVC classifiers with per-label checkpoints.

    This helper is intentionally sequential. A single shared sparse feature matrix
    stays resident in memory, which avoids process-based duplication of a ~50k
    TF-IDF matrix in Colab. Each completed label is written immediately, so a
    disconnect can lose at most the currently-running classifier rather than an
    entire batch (the previous notebook used 100-classifier checkpoint blocks).

    The returned score matrices have shape ``(n_rows, n_labels)`` and preserve
    ``labels`` order exactly. Existing per-label checkpoints are validated by
    label identity, index, row counts, finite scores, and non-zero file size
    before they are reused.
    """
    checkpoint_dir = Path(checkpoint_dir)
    checkpoint_dir.mkdir(parents=True, exist_ok=True)
    n_labels = len(labels)
    if y_train.shape[1] != n_labels:
        raise ValueError(f"y_train has {y_train.shape[1]} columns but {n_labels} labels were supplied")
    if x_train.shape[0] != y_train.shape[0]:
        raise ValueError("x_train and y_train row counts differ")

    validation_scores = np.empty((x_validation.shape[0], n_labels), dtype=np.float32)
    test_scores = np.empty((x_test.shape[0], n_labels), dtype=np.float32)
    metadata: list[dict[str, Any] | None] = [None] * n_labels

    reusable = 0
    for label_index, label in enumerate(labels):
        loaded = _load_label_checkpoint(
            _checkpoint_path(checkpoint_dir, label_index),
            label=label,
            label_index=label_index,
            validation_rows=x_validation.shape[0],
            test_rows=x_test.shape[0],
        )
        if loaded is None:
            continue
        validation_scores[:, label_index] = loaded["validation_scores"]
        test_scores[:, label_index] = loaded["test_scores"]
        metadata[label_index] = {
            "label": label,
            "label_index": label_index,
            "status": "reused",
            **{k: v for k, v in loaded.items() if k not in {"validation_scores", "test_scores"}},
        }
        reusable += 1

    print(f"checkpoint reuse: completed classifiers: {reusable} / {n_labels}")
    run_started = time.monotonic()

    for label_index, label in enumerate(labels):
        if metadata[label_index] is not None:
            continue

        y_binary = _binary_column(y_train, label_index)
        positives = int(y_binary.sum())
        negatives = int(y_binary.size - positives)
        if positives == 0 or negatives == 0:
            raise ValueError(
                f"Label {label_index}/{n_labels} {label!r} has an invalid training target: "
                f"positives={positives}, negatives={negatives}"
            )

        fit_started = time.monotonic()
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always", ConvergenceWarning)
            classifier = LinearSVC(
                class_weight=class_weight,
                random_state=random_state,
                max_iter=max_iter,
                tol=tol,
                dual="auto",
            )
            classifier.fit(x_train, y_binary)
        elapsed = time.monotonic() - fit_started
        converged = not any(issubclass(item.category, ConvergenceWarning) for item in caught)
        n_iter = int(np.max(np.atleast_1d(classifier.n_iter_)))
        val = np.asarray(classifier.decision_function(x_validation), dtype=np.float32).reshape(-1)
        tst = np.asarray(classifier.decision_function(x_test), dtype=np.float32).reshape(-1)

        checkpoint = _checkpoint_path(checkpoint_dir, label_index)
        _save_label_checkpoint(
            checkpoint,
            label=label,
            label_index=label_index,
            validation_scores=val,
            test_scores=tst,
            n_iter=n_iter,
            converged=converged,
            elapsed_seconds=elapsed,
            train_positive=positives,
        )
        validation_scores[:, label_index] = val
        test_scores[:, label_index] = tst
        metadata[label_index] = {
            "label": label,
            "label_index": label_index,
            "status": "fitted",
            "n_iter": n_iter,
            "converged": converged,
            "elapsed_seconds": elapsed,
            "train_positive": positives,
        }

        completed = sum(item is not None for item in metadata)
        _atomic_json(
            checkpoint_dir / "progress.json",
            {
                "status": "IN_PROGRESS" if completed < n_labels else "CLASSIFIERS_COMPLETE",
                "completed_classifiers": completed,
                "total_classifiers": n_labels,
                "last_completed_label_index": label_index,
                "last_completed_label": label,
                "elapsed_this_session_seconds": time.monotonic() - run_started,
                "linear_svc": {
                    "class_weight": class_weight,
                    "random_state": random_state,
                    "max_iter": max_iter,
                    "tol": tol,
                    "dual": "auto",
                },
            },
        )
        if progress_every > 0 and (completed % progress_every == 0 or completed == n_labels):
            convergence = "OK" if converged else "MAX_ITER_REACHED"
            print(
                f"classifier progress: {completed} / {n_labels} | "
                f"label_index={label_index} | train_positive={positives} | "
                f"fit={elapsed:.1f}s | n_iter={n_iter} | {convergence} | checkpoint saved",
                flush=True,
            )

    final_metadata = [item for item in metadata if item is not None]
    if len(final_metadata) != n_labels:
        raise RuntimeError(f"Only {len(final_metadata)} / {n_labels} classifiers are available after fitting")
    _atomic_json(
        checkpoint_dir / "progress.json",
        {
            "status": "CLASSIFIERS_COMPLETE",
            "completed_classifiers": n_labels,
            "total_classifiers": n_labels,
            "elapsed_this_session_seconds": time.monotonic() - run_started,
            "non_converged_classifiers": [
                item["label"] for item in final_metadata if not bool(item["converged"])
            ],
            "linear_svc": {
                "class_weight": class_weight,
                "random_state": random_state,
                "max_iter": max_iter,
                "tol": tol,
                "dual": "auto",
            },
        },
    )
    return validation_scores, test_scores, final_metadata
