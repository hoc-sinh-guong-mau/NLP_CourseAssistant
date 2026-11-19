"""Comparison, gold audits and isolation must not silently change benchmark scores."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from src.application.pipeline import CourseAssistant
from src.evaluation.dataset import load_cases
from src.evaluation.evaluator import evaluate
from src.evaluation.exceptions import EvaluationError


def record(status="ok", **extra):
    return {"status": status, "parse_tree": "(S)" if status == "ok" else "()", **extra}


class EvaluationComparisonTests(unittest.TestCase):
    def write(self, directory, rows):
        path = Path(directory) / "cases.jsonl"
        path.write_text(
            "".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8"
        )
        return path

    def test_reports_recoveries_and_regressions_with_identical_case_order(self):
        with tempfile.TemporaryDirectory() as directory:
            cases = [
                {
                    "id": str(i),
                    "tags": ["paraphrase"],
                    "input": str(i),
                    "expected": {"status": "ok"},
                }
                for i in range(3)
            ]
            path = self.write(directory, cases)
            baseline = Mock(statistical_recognizer=None)
            baseline.process.side_effect = [record("parse_failed"), record(), record()]
            assistant = Mock(statistical_recognizer=None)
            assistant.process.side_effect = [
                record(statistical_used=True),
                record("parse_failed"),
                record(),
            ]
            report = evaluate(
                assistant,
                cases_path=path,
                output_path=Path(directory) / "evaluation.txt",
                compare=True,
                baseline=baseline,
            )
            self.assertEqual((report["passed"], report["total"]), (2, 3))
            self.assertEqual(len(report["comparison"]["recovered_turns"]), 1)
            self.assertEqual(len(report["comparison"]["regressed_turns"]), 1)
            self.assertEqual(report["groups"]["paraphrase"]["count"], 3)
            self.assertEqual(len(report["failures"]), 2)
            self.assertEqual(
                [call.args for call in baseline.process.call_args_list],
                [call.args for call in assistant.process.call_args_list],
            )
            self.assertEqual(report["comparison"]["grammar_only"]["passed"], 2)
            self.assertIn("warning", report["comparison"])

    def test_gold_conflict_is_visible_without_selecting_a_convenient_label(self):
        semantic = {
            "predicate": "GET_ASSIGNMENT",
            "qtype": "DOMAIN",
            "arguments": {"assignment_id": "BTL01"},
        }
        intent_entity = {
            "intent": "GET_ASSIGNMENT",
            "qtype": "TITLE",
            "entities": {"assignment_id": "BTL01"},
        }
        with tempfile.TemporaryDirectory() as directory:
            path = self.write(
                directory,
                [
                    {
                        "input": "q",
                        "expected": {
                            "status": "ok",
                            "semantic": semantic,
                            "intent_entity": intent_entity,
                        },
                    }
                ],
            )
            observed = record(
                semantic=semantic, intent_entity={**intent_entity, "qtype": "DOMAIN"}
            )
            report = evaluate(
                Mock(process=Mock(return_value=observed), statistical_recognizer=None),
                cases_path=path,
                output_path=Path(directory) / "evaluation.txt",
            )
            self.assertEqual(report["passed"], 0)
            self.assertTrue(report["cases"][0]["checks"]["semantic"])
            self.assertFalse(report["cases"][0]["checks"]["intent_entity"])
            self.assertEqual(
                report["dataset_metadata"]["annotation_warnings"][0]["fields"],
                ["qtype"],
            )
            self.assertIsNone(report["task_performance"]["qtype_classification"])
            self.assertEqual(
                report["task_performance"]["intent_classification"]["accuracy"], 1
            )

    def test_invalid_json_schema_and_case_ids_are_rejected(self):
        rows = [
            {"input": "q", "expected": {"sttaus": "ok"}},
            {"input": "q", "expected": {"entities": {"topic_ids": []}}},
            {"turns": []},
            {
                "input": "q",
                "expected": {"status": "ok"},
                "turns": [{"input": "q", "expected": {"status": "ok"}}],
            },
        ]
        with tempfile.TemporaryDirectory() as directory:
            for case in rows:
                with self.subTest(case=case), self.assertRaises(EvaluationError):
                    load_cases(self.write(directory, [case]))
            path = self.write(
                directory,
                [{"id": "same", "input": "q", "expected": {"status": "ok"}}] * 2,
            )
            with self.assertRaises(EvaluationError):
                load_cases(path)
            path.write_text("\n{bad json}\n", encoding="utf-8")
            with self.assertRaises(EvaluationError) as error:
                load_cases(path)
            self.assertEqual(error.exception.context["line"], 2)
            path.write_text(
                '{"input":"q","expected":{"parse_count":NaN}}', encoding="utf-8"
            )
            with self.assertRaises(EvaluationError):
                load_cases(path)

    def test_duplicate_inputs_are_audited_without_dropping_cases(self):
        with tempfile.TemporaryDirectory() as directory:
            path = self.write(
                directory,
                [
                    {"input": "NLP có mấy tín chỉ?", "expected": {"status": "ok"}},
                    {"input": "NLP   có mấy tín chỉ???", "expected": {"status": "ok"}},
                ],
            )
            cases, metadata = load_cases(path)
            self.assertEqual(len(cases), 2)
            self.assertEqual(
                metadata["annotation_warnings"][0]["kind"], "duplicate_normalized_input"
            )
            self.assertEqual(len(metadata["sha256"]), 64)

    def test_dialogue_sessions_reset_between_cases_and_comparison_modes(self):
        cases = [
            {
                "id": "context",
                "turns": [
                    {
                        "input": "Bài tập lớn có phần parser không?",
                        "expected": {"status": "ok"},
                    },
                    {
                        "input": "Phần này cần xuất file gì?",
                        "expected": {
                            "status": "ok",
                            "context_used": {"source_turn": 1},
                        },
                    },
                ],
            },
            {
                "id": "reset",
                "turns": [
                    {
                        "input": "Phần này cần xuất file gì?",
                        "expected": {"status": "needs_context"},
                    }
                ],
            },
        ]
        with tempfile.TemporaryDirectory() as directory:
            path = self.write(directory, cases)
            report = evaluate(
                CourseAssistant(use_statistical=False),
                cases_path=path,
                output_path=Path(directory) / "evaluation.txt",
                compare=True,
            )
            self.assertEqual((report["passed"], report["total"]), (2, 2))
            self.assertEqual(report["dialogue_performance"]["sessions"]["accuracy"], 1)
            self.assertEqual(
                report["comparison"]["grammar_only"]["dialogue_performance"][
                    "sessions"
                ]["accuracy"],
                1,
            )
            self.assertEqual(
                report["cases"][1]["turns"][0]["actual"]["context_before"]["entities"],
                {},
            )

    def test_processing_failures_propagate_without_a_partial_report(self):
        with tempfile.TemporaryDirectory() as directory:
            path = self.write(directory, [{"input": "q", "expected": {"status": "ok"}}])
            assistant = Mock(statistical_recognizer=None)
            assistant.process.side_effect = RuntimeError("system failure")
            with self.assertRaisesRegex(RuntimeError, "system failure"):
                evaluate(
                    assistant,
                    cases_path=path,
                    output_path=Path(directory) / "evaluation.txt",
                )
            self.assertFalse((Path(directory) / "evaluation.txt").exists())
