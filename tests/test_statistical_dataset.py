import json
import tempfile
import unittest
from pathlib import Path

from src.statistical_processing.dataset import load_labeled_dataset, split_labeled_dataset


class StatisticalDatasetTests(unittest.TestCase):
    def test_stratified_splits_are_disjoint_and_cover_each_qtype(self):
        labels = [
            ("GET_COURSE_INFO", "CREDITS"),
            ("GET_DEADLINE", "DEADLINE"),
            ("GET_SCHEDULE", "WEEK_CONTENT"),
        ]
        records = [
            {
                "sentence": f"example {intent.lower()} {index}",
                "intent": intent,
                "qtype": qtype,
                "source": "test",
            }
            for intent, qtype in labels
            for index in range(12)
        ]

        first = split_labeled_dataset(records, seed=19)
        second = split_labeled_dataset(records, seed=19)
        self.assertEqual(first, second)
        sentence_sets = {
            name: {record["sentence"] for record in rows}
            for name, rows in first.items()
        }
        self.assertFalse(sentence_sets["train"] & sentence_sets["validation"])
        self.assertFalse(sentence_sets["train"] & sentence_sets["test"])
        self.assertFalse(sentence_sets["validation"] & sentence_sets["test"])
        for rows in first.values():
            self.assertEqual({record["qtype"] for record in rows}, {qtype for _, qtype in labels})

    def test_json_loader_checks_required_labels(self):
        valid = [{
            "sentence": "Môn NLP có mấy tín chỉ?",
            "intent": "GET_COURSE_INFO",
            "qtype": "CREDITS",
        }]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory, "dataset.json")
            path.write_text(json.dumps(valid), encoding="utf-8")
            self.assertEqual(load_labeled_dataset(path), valid)

            path.write_text(json.dumps([{**valid[0], "qtype": "UNSUPPORTED"}]), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "unsupported label"):
                load_labeled_dataset(path)


if __name__ == "__main__":
    unittest.main()
