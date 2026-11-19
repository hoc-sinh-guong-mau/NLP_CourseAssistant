"""Preserve useful main-branch evaluation behavior under the schema-3 contract."""

import json
import tempfile
import unittest
from pathlib import Path

from src.config import ROOT
from src.evaluation.dataset import load_cases
from src.evaluation.exceptions import EvaluationError
from src.evaluation.metrics import comparison, summarize
from src.evaluation.scoring import query_key, score


def record(**extra):
    return {
        "status": "ok",
        "semantic": {
            "predicate": "GET_COURSE_INFO",
            "qtype": "CREDITS",
            "arguments": {"course_id": "CO3085"},
        },
        "intent_entity": {
            "intent": "GET_COURSE_INFO",
            "qtype": "CREDITS",
            "entities": {"course_id": "CO3085"},
        },
        **extra,
    }


def row(expected, actual):
    return {
        "case_id": "one",
        "turn": 1,
        "input": "q",
        "elapsed_ms": 1,
        "tags": ["example"],
        **score(expected, actual),
    }


class IntegratedEvaluationTests(unittest.TestCase):
    def test_main_fixture_loads_with_dialogue_and_outside_domain_labels(self):
        cases, metadata = load_cases(ROOT / "input/evaluation_cases.jsonl")
        self.assertEqual(len(cases), 42)
        self.assertEqual(metadata["case_count"], len(cases))
        self.assertTrue(any(case["dialogue"] for case in cases))
        self.assertTrue(any("outside_domain" in case["tags"] for case in cases))

    def test_unknown_labels_score_rejection_without_changing_pipeline_output(self):
        actual = record(status="parse_failed", semantic=None, intent_entity=None)
        result = score(
            {"intent": "UNKNOWN", "qtype": "UNKNOWN", "entities": {}}, actual
        )
        self.assertTrue(result["correct"])
        self.assertIsNone(actual["intent_entity"])
        self.assertIsNone(actual["semantic"])

    def test_unknown_false_acceptance_includes_explicit_null_gold(self):
        rows = [
            row({"intent_entity": None}, record()),
            row({"intent": "UNKNOWN"}, record(semantic=None, intent_entity=None)),
        ]
        task = summarize(rows)["task_performance"]
        self.assertEqual(
            task["unknown_requests"],
            {"count": 2, "false_accepts": 1, "false_acceptance_rate": 0.5},
        )
        self.assertEqual(task["intent_classification"]["count"], 2)
        self.assertEqual(task["intent_classification"]["accuracy"], 0.5)

    def test_semantic_frame_metric_is_independent_of_intent_entity_labels(self):
        expected = {
            "intent": "GET_COURSE_INFO",
            "qtype": "CREDITS",
            "entities": {"course_id": "CO3085"},
        }
        wrong = {
            "predicate": "GET_COURSE_INFO",
            "qtype": "CREDITS",
            "arguments": {"course_id": "WRONG"},
        }
        task = summarize([row(expected, record(semantic=wrong))])["task_performance"]
        self.assertEqual(task["intent_classification"]["accuracy"], 1)
        self.assertEqual(task["entity_extraction_exact_match_accuracy"], 1)
        self.assertEqual(task["semantic_frame_accuracy"]["accuracy"], 0)

    def test_logical_query_metric_preserves_legacy_exact_check(self):
        query = {
            "collection": "course",
            "filters": {"id": "CO3085"},
            "select": ["id", "credits"],
        }
        reordered = {**query, "select": ["credits", "id"]}
        result = row({"query": query}, record(query=reordered))
        self.assertFalse(result["checks"]["query"])
        self.assertEqual(
            summarize([result])["task_performance"]["query_logical_equivalence"][
                "accuracy"
            ],
            1,
        )
        self.assertNotEqual(
            query_key(query), query_key({**query, "filters": {"id": "WRONG"}})
        )

    def test_unknown_and_semantic_metrics_do_not_invent_unannotated_labels(self):
        task = summarize([row({"status": "ok"}, record())])["task_performance"]
        self.assertEqual(task["unknown_requests"]["count"], 0)
        self.assertIsNone(task["unknown_requests"]["false_acceptance_rate"])
        self.assertEqual(task["semantic_frame_accuracy"]["count"], 0)
        self.assertIsNone(task["query_logical_equivalence"]["accuracy"])

    def test_groups_count_both_sessions_and_turns_and_comparison_counts_wrong_fallback(
        self,
    ):
        turns = [
            row({"status": "ok"}, record()),
            row({"status": "ok"}, record(status="parse_failed", statistical_used=True)),
        ]
        case = {"tags": ["dialogue"], "correct": False, "turns": turns}
        summary = summarize([case])
        self.assertEqual(summary["groups"]["dialogue"]["count"], 1)
        self.assertEqual(summary["group_turns"]["dialogue"]["count"], 2)
        compared = comparison([case], [case])
        self.assertEqual(compared["evaluated_turns"], 2)
        self.assertEqual(compared["fallback_accepted_incorrect_turns"], 1)

    def test_malformed_main_labels_are_rejected_before_execution(self):
        invalid = [
            {"query": "SELECT *"},
            {"parse_count": True},
            {"parse_count": -1},
            {"statistical_used": 1},
            {"semantic": {"wrong": "keys"}},
        ]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "cases.jsonl"
            for expected in invalid:
                with self.subTest(expected=expected):
                    path.write_text(json.dumps({"input": "q", "expected": expected}))
                    with self.assertRaises(EvaluationError):
                        load_cases(path)
