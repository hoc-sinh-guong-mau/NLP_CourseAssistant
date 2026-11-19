"""Acceptance examples from course-assistant.pdf, section 2 (page 2)."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from src.application.pipeline import CourseAssistant
from src.evaluation.evaluator import evaluate
from src.evaluation.exceptions import EvaluationError
from src.parsing import Parser, validate_grammar
from src.parsing.exceptions import GrammarError
from src.preprocessing import normalize, tokenize
from src.semantic import SemanticInterpreter


class AssignmentAcceptanceTests(unittest.TestCase):
    def test_reversed_part_relations_match_the_tokenizer(self):
        assistant = CourseAssistant(use_statistical=False)
        for text, part in [
            ("BTL yêu cầu phần I là gì?", "PART_I"),
            ("Bài tập lớn quy định phần II là gì?", "PART_II"),
        ]:
            with self.subTest(text=text):
                result = assistant.process(text)
                self.assertEqual(result["semantic"]["qtype"], "PART_INFO")
                self.assertEqual(
                    result["semantic"]["arguments"],
                    {"assignment_id": "BTL01", "part_id": part},
                )
        with self.assertRaises(GrammarError):
            validate_grammar("% start S\nS -> 'yêu cầu'")

    def test_all_official_examples_have_a_symbolic_semantic_interpretation(self):
        examples = [
            (
                "Môn NLP có bao nhiêu tín chỉ?",
                "GET_COURSE_INFO",
                "CREDITS",
                {"course_id": "CO3085"},
            ),
            (
                "Tuần 5 học những nội dung gì?",
                "GET_SCHEDULE",
                "WEEK_CONTENT",
                {"week_id": "WEEK_05"},
            ),
            (
                "Phần CFG và Parsing nằm ở tuần nào?",
                "GET_SCHEDULE",
                "TOPICS_WEEK",
                {"topic_ids": ["CFG", "PARSING"]},
            ),
            (
                "Bài tập lớn có những yêu cầu gì?",
                "GET_ASSIGNMENT",
                "REQUIREMENTS",
                {"assignment_id": "BTL01"},
            ),
            (
                "Deadline của bài tập lớn là khi nào?",
                "GET_DEADLINE",
                "DEADLINE",
                {"assignment_id": "BTL01"},
            ),
            (
                "Tài liệu nào nói về CFG?",
                "GET_RESOURCE",
                "RESOURCE_BY_TOPIC",
                {"topic_id": "CFG"},
            ),
            (
                "Bài tập lớn có được sử dụng công cụ AI không?",
                "GET_RULE",
                "PERMISSION",
                {"rule_id": "AI_USAGE", "assignment_id": "BTL01"},
            ),
            (
                "Tôi cần hoàn thành những bài tập nào?",
                "GET_ASSIGNMENT",
                "ASSIGNMENT_LIST",
                {"course_id": "CO3085"},
            ),
        ]
        parser = Parser()
        semantic = SemanticInterpreter()
        for text, intent, qtype, arguments in examples:
            with self.subTest(text=text):
                trees = parser.parse_all(tokenize(normalize(text)))
                self.assertTrue(trees)
                frames = [semantic.interpret(tree) for tree in trees]
                self.assertEqual(len({frame.canonical_key() for frame in frames}), 1)
                self.assertEqual(
                    frames[0].to_dict(),
                    {"predicate": intent, "qtype": qtype, "arguments": arguments},
                )

    def test_nominal_assignment_fields_generalize_across_aliases(self):
        assistant = CourseAssistant(use_statistical=False)
        for text, qtype in [
            ("Mục tiêu của bài tập lớn là gì?", "GOAL"),
            ("Mục đích của BTL là gì?", "GOAL"),
            ("Tên gọi của BTL01 là gì?", "TITLE"),
            ("Đầu ra của bài tập lớn là gì?", "OUTPUTS"),
            ("Miền dữ liệu của BTL là gì?", "DOMAIN"),
            ("BTL có các yêu cầu cụ thể nào?", "REQUIREMENTS"),
        ]:
            with self.subTest(text=text):
                record = assistant.process(text)
                self.assertEqual(record["semantic"]["qtype"], qtype)
                self.assertEqual(
                    record["semantic"]["arguments"], {"assignment_id": "BTL01"}
                )
                self.assertFalse(record["statistical_used"])
        for text in ("Mục tiêu của ngành y là gì?", "Thời tiết hôm nay thế nào?"):
            with self.subTest(text=text):
                self.assertEqual(assistant.process(text)["status"], "parse_failed")

    def test_combined_evaluation_reports_counts_examples_and_method_limitations(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            flat = root / "flat.jsonl"
            dialogue = root / "dialogue.jsonl"
            flat.write_text(
                json.dumps(
                    {
                        "id": "question",
                        "input": "a",
                        "expected": {"status": "ok", "answer": "correct"},
                    }
                )
                + "\n"
            )
            dialogue.write_text(
                json.dumps(
                    {
                        "id": "conversation",
                        "turns": [{"input": "b", "expected": {"status": "ok"}}],
                    }
                )
                + "\n"
            )
            assistant = Mock(statistical_recognizer=None)
            assistant.process.side_effect = [
                {"status": "ok", "answer": "wrong"},
                {"status": "parse_failed"},
            ]
            report = evaluate(
                assistant,
                cases_path=flat,
                dialogue_cases_path=dialogue,
                output_path=root / "evaluation.txt",
            )
            self.assertEqual((report["total"], report["passed"]), (2, 0))
            self.assertEqual(report["dataset_metadata"]["combined_turn_count"], 2)
            self.assertEqual(report["answer_performance"]["exact_text"]["correct"], 0)
            self.assertEqual(
                report["error_analysis"]["primary"]["counts"]["answer_mismatch"], 1
            )
            self.assertEqual(
                report["error_analysis"]["primary"]["counts"]["grammar_no_parse"], 1
            )
            self.assertTrue(all(row["explanation"] for row in report["failures"]))
            self.assertTrue(report["method_notes"]["limitations"])
            self.assertTrue(report["method_notes"]["strengths"])

    def test_supplemental_cases_must_be_distinct_dialogues(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            flat = root / "a.jsonl"
            extra = root / "b.jsonl"
            flat.write_text('{"id":"same","input":"a","expected":{"status":"ok"}}\n')
            extra.write_text('{"id":"other","input":"b","expected":{"status":"ok"}}\n')
            with self.assertRaises(EvaluationError):
                evaluate(
                    Mock(),
                    cases_path=flat,
                    dialogue_cases_path=extra,
                    output_path=root / "out.txt",
                )
            extra.write_text(
                '{"id":"same","turns":[{"input":"b","expected":{"status":"ok"}}]}\n'
            )
            with self.assertRaises(EvaluationError):
                evaluate(
                    Mock(),
                    cases_path=flat,
                    dialogue_cases_path=extra,
                    output_path=root / "out.txt",
                )
            with self.assertRaises(EvaluationError):
                evaluate(
                    Mock(),
                    cases_path=flat,
                    dialogue_cases_path=extra,
                    output_path=extra,
                )
