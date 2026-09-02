from __future__ import annotations
from collections import Counter
from typing import Any, Mapping, Sequence

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
