from __future__ import annotations
import unittest

from src.experiments.level2 import support_threshold_analysis


def row(record_id: str, source: str, labels: list[str]) -> dict:
    return {
        "canonical_record_id": record_id,
        "source": source,
        "target_labels": labels,
    }


class Level2SupportThresholdTests(unittest.TestCase):
    def analyse(self, train, validation, test, *, source="papers_with_code", thresholds=(2,)):
        return support_threshold_analysis(
            train_rows=train,
            validation_rows=validation,
            test_rows=test,
            source=source,
            thresholds=thresholds,
        )

    def test_training_support_determines_eligibility(self):
        result = self.analyse(
            [row("t1", "papers_with_code", ["A"]), row("t2", "papers_with_code", ["A"])],
            [row("v1", "papers_with_code", ["B"]), row("v2", "papers_with_code", ["B"])],
            [row("x1", "papers_with_code", ["B"]), row("x2", "papers_with_code", ["B"])],
        )[0]
        self.assertEqual(result["eligible_labels"], ["A"])

    def test_train_eligible_label_remains_when_test_support_is_zero(self):
        result = self.analyse(
            [row("t1", "papers_with_code", ["A"]), row("t2", "papers_with_code", ["A"])],
            [row("v1", "papers_with_code", ["A"])],
            [row("x1", "papers_with_code", ["B"])],
        )[0]
        self.assertIn("A", result["eligible_labels"])
        self.assertEqual(result["partition_label_support"]["test"]["A"], 0)

    def test_total_support_cannot_promote_label_below_training_threshold(self):
        result = self.analyse(
            [row("t1", "papers_with_code", ["B"])],
            [row(f"v{i}", "papers_with_code", ["B"]) for i in range(3)],
            [row(f"x{i}", "papers_with_code", ["B"]) for i in range(3)],
        )[0]
        self.assertEqual(result["eligible_labels"], [])
        self.assertEqual(result["validation_retained_records"], 0)
        self.assertEqual(result["test_retained_records"], 0)

    def test_validation_and_test_support_cannot_demote_train_eligible_label(self):
        result = self.analyse(
            [row("t1", "papers_with_code", ["A"]), row("t2", "papers_with_code", ["A"])],
            [],
            [],
        )[0]
        self.assertEqual(result["eligible_labels"], ["A"])
        self.assertEqual(result["validation_retained_records"], 0)
        self.assertEqual(result["test_retained_records"], 0)

    def test_records_with_no_retained_labels_are_removed_after_filtering(self):
        result = self.analyse(
            [row("t1", "papers_with_code", ["A"]), row("t2", "papers_with_code", ["A"])],
            [
                row("v1", "papers_with_code", ["A", "B"]),
                row("v2", "papers_with_code", ["B"]),
            ],
            [row("x1", "papers_with_code", ["B"])],
        )[0]
        self.assertEqual(result["validation_retained_records"], 1)
        self.assertEqual(result["validation_label_assignments"], 1)
        self.assertEqual(result["test_retained_records"], 0)

    def test_same_eligible_vocabulary_is_used_for_all_partitions(self):
        result = self.analyse(
            [
                row("t1", "papers_with_code", ["A"]),
                row("t2", "papers_with_code", ["A"]),
                row("t3", "papers_with_code", ["B"]),
                row("t4", "papers_with_code", ["B"]),
            ],
            [row("v1", "papers_with_code", ["A"])],
            [row("x1", "papers_with_code", ["B"])],
        )[0]
        expected = set(result["eligible_labels"])
        self.assertEqual(expected, {"A", "B"})
        for partition in ("train", "validation", "test"):
            self.assertEqual(set(result["partition_label_support"][partition]), expected)

    def test_thresholds_5_10_20_are_independent(self):
        train = []
        for label, count in (("A", 20), ("B", 10), ("C", 5), ("D", 4)):
            train.extend(row(f"{label}{i}", "papers_with_code", [label]) for i in range(count))
        results = self.analyse(train, [], [], thresholds=(5, 10, 20))
        self.assertEqual([r["eligible_label_count"] for r in results], [3, 2, 1])
        self.assertEqual(results[0]["eligible_labels"], ["A", "B", "C"])
        self.assertEqual(results[1]["eligible_labels"], ["A", "B"])
        self.assertEqual(results[2]["eligible_labels"], ["A"])

    def test_source_specific_level2_spaces_remain_separate(self):
        train = [
            row("p1", "papers_with_code", ["PWC"]),
            row("p2", "papers_with_code", ["PWC"]),
            row("b1", "bio.tools", ["EDAM"]),
            row("b2", "bio.tools", ["EDAM"]),
        ]
        pwc = self.analyse(train, [], [], source="papers_with_code")[0]
        bio = self.analyse(train, [], [], source="bio.tools")[0]
        self.assertEqual(pwc["eligible_labels"], ["PWC"])
        self.assertEqual(bio["eligible_labels"], ["EDAM"])

    def test_validation_test_support_neither_promotes_nor_changes_training_support(self):
        train = [
            row("t1", "papers_with_code", ["A"]),
            row("t2", "papers_with_code", ["A"]),
            row("t3", "papers_with_code", ["B"]),
        ]
        validation = [row(f"v{i}", "papers_with_code", ["B"]) for i in range(10)]
        test = [row(f"x{i}", "papers_with_code", ["B"]) for i in range(10)]
        result = self.analyse(train, validation, test)[0]
        self.assertEqual(result["eligible_labels"], ["A"])
        self.assertEqual(result["training_support"], {"A": 2})


if __name__ == "__main__":
    unittest.main()
