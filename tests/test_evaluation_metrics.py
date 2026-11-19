"""Gold coverage and counts, independent of model predictions or grammar wording."""

import unittest

from src.evaluation.metrics import _abstention_metrics, _intent_metrics, summarize
from src.evaluation.scoring import score


def actual(intent="GET_COURSE_INFO", qtype="CREDITS", entities=None, **extra):
    entities = {"course_id": "CO3085"} if entities is None else entities
    return {
        "status": "ok",
        "parse_tree": "(S)",
        "semantic": {"predicate": intent, "qtype": qtype, "arguments": entities},
        "intent_entity": {"intent": intent, "qtype": qtype, "entities": entities},
        **extra,
    }


def row(expected, observed):
    return {
        "id": "one",
        "tags": ["test"],
        "case_id": "one",
        "turn": 1,
        "input": "q",
        "elapsed_ms": 1,
        **score(expected, observed),
    }


class EvaluationMetricsTests(unittest.TestCase):
    def test_qtype_and_intent_are_scored_separately(self):
        metrics = summarize(
            [
                row(
                    {"intent": "GET_COURSE_INFO", "qtype": "CREDITS"},
                    actual(qtype="DESCRIPTION"),
                )
            ]
        )
        self.assertEqual(
            metrics["task_performance"]["intent_classification"]["accuracy"], 1
        )
        self.assertEqual(
            metrics["task_performance"]["qtype_classification"]["accuracy"], 0
        )
        self.assertEqual(
            metrics["task_performance"]["field_accuracy"]["qtype"]["count"], 1
        )

    def test_entities_penalize_wrong_ids_and_hallucinated_slots(self):
        metrics = summarize(
            [
                row(
                    {"entities": {"topic_ids": ["CFG", "PARSING"]}},
                    actual(entities={"topic_ids": ["PARSING", "CFG"]}),
                ),
                row(
                    {"entities": {"week_id": "WEEK_03"}},
                    actual(entities={"week_id": "WEEK_04"}),
                ),
                row({"entities": {}}, actual()),
            ]
        )["task_performance"]
        micro = metrics["entity_extraction_micro"]
        self.assertEqual(
            (micro["true_positive"], micro["false_positive"], micro["false_negative"]),
            (2, 2, 1),
        )
        self.assertAlmostEqual(micro["precision"], 0.5)
        self.assertAlmostEqual(micro["recall"], 2 / 3)
        self.assertAlmostEqual(micro["f1"], 4 / 7)
        # Micro matches unordered ID sets; the legacy exact check remains strict.
        self.assertEqual(metrics["entity_extraction_exact_match_accuracy"], 0)

    def test_absent_annotations_are_not_counted_as_model_errors(self):
        metrics = summarize([row({"status": "ok"}, actual())])
        self.assertIsNone(metrics["task_performance"]["qtype_classification"])
        self.assertEqual(metrics["task_performance"]["entity_extraction_count"], 0)
        self.assertIsNone(metrics["task_performance"]["entity_extraction_micro"]["f1"])
        self.assertEqual(metrics["dialogue_performance"]["sessions"]["count"], 0)
        self.assertIsNone(metrics["fallback_performance"]["acceptance_rate"])

    def test_legacy_abstention_convention_and_binary_decisions_are_distinct(self):
        rows = [
            row({"abstain": False, "answer": "correct"}, actual(answer="wrong")),
            row({"abstain": True}, actual(status="needs_context")),
        ]
        metrics = summarize(rows)["abstention_performance"]
        self.assertEqual(metrics["outcomes"]["N2_incorrect_answer"], 1)
        self.assertEqual(metrics["outcomes"]["N5_correct_abstention"], 1)
        self.assertEqual(metrics["abstention_recall"], 0.5)
        self.assertEqual(metrics["binary_decision"]["recall"], 1)
        self.assertEqual(metrics["binary_decision"]["accuracy"], 1)
        self.assertEqual(metrics["abstention_accuracy"], 0.5)

    def test_mismatched_metric_arrays_fail_explicitly(self):
        with self.assertRaises(ValueError):
            _intent_metrics(["A"], [])
        with self.assertRaises(ValueError):
            _abstention_metrics([True], [], [])

    def test_evidence_and_answer_checks_are_independent(self):
        result = row(
            {"result_contains": [{"credits": 3}], "answer_contains": ["3 tín chỉ"]},
            actual(
                result=[{"credits": 3, "id": "CO3085"}], answer="Môn học có 4 tín chỉ."
            ),
        )
        self.assertTrue(result["checks"]["result_contains"])
        self.assertFalse(result["checks"]["answer_contains"])
        self.assertFalse(result["correct"])
        self.assertFalse(
            score({"context_used": {}}, actual(context_used={"source_turn": 1}))[
                "correct"
            ]
        )
