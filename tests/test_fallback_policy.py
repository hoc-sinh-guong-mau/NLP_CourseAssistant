"""Fallback must have grounded question evidence, even at high confidence."""

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

from src.application.pipeline import CourseAssistant
from src.config import LEXICON_DIR
from src.dialogue import DialogueSession
from src.lexical import Lexicon
from src.retrieval.sqlite import SQLiteKnowledgeBase, build_sqlite
from src.semantic.rules import SEMANTIC_RULES
from src.statistical_processing.entity_extractor import EntityExtractor
from src.statistical_processing.fallback_policy import QTYPE_CUES, FallbackPolicy


class FallbackPolicyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = tempfile.TemporaryDirectory()
        path = Path(cls.directory.name) / "kb.sqlite3"
        build_sqlite(database=path)
        cls.kb = SQLiteKnowledgeBase(path)
        cls.lexicon = Lexicon.load(LEXICON_DIR)
        cls.policy = FallbackPolicy(cls.lexicon, minimum_confidence=0.05)
        cls.assistant = CourseAssistant(kb=cls.kb)

    @classmethod
    def tearDownClass(cls):
        cls.directory.cleanup()

    def forced(self, qtype, confidence=0.99):
        predictor = SimpleNamespace(
            unknown_threshold=0.05,
            predict_with_confidence=Mock(return_value=(qtype, confidence)),
        )
        parser = Mock()
        parser.parse_all.return_value = []
        return CourseAssistant(
            kb=self.kb, parser=parser, statistical_recognizer=predictor
        )

    def test_every_registered_qtype_has_an_evidence_policy(self):
        self.assertEqual(set(QTYPE_CUES), {qtype for _, qtype in SEMANTIC_RULES})

    def test_wrong_question_focus_is_rejected_even_at_high_confidence(self):
        for text, qtype in [
            ("Học phí môn NLP là bao nhiêu?", "COURSE_NAME"),
            ("NLP có bao nhiêu bàn thắng?", "CHAPTER_COUNT"),
            ("NLP là nhà hàng gì?", "COURSE_NAME"),
            ("Bài tập lớn phải nộp qua hệ thống nào?", "DEADLINE"),
        ]:
            with self.subTest(text=text):
                result = self.forced(qtype).process(text)
                self.assertEqual(result["status"], "parse_failed")
                self.assertEqual(
                    result["fallback_validation"]["reason"], "missing_qtype_evidence"
                )
                self.assertIsNone(result["semantic"])
                self.assertIsNone(result["query"])
                self.assertFalse(result["statistical_used"])

    def test_an_explicit_foreign_course_is_not_a_default_assignment_or_reference(self):
        for text, qtype in [
            ("Bài tập lớn môn Toán yêu cầu gì?", "REQUIREMENTS"),
            ("Môn Cơ sở dữ liệu có bao nhiêu chương?", "COURSE_CHAPTER_COUNT"),
            ("Deadline bài tập lớn môn Lập trình nâng cao là khi nào?", "DEADLINE"),
            ("BTL môn CO9999 có tên gì?", "TITLE"),
        ]:
            with self.subTest(text=text):
                result = self.forced(qtype).process(text)
                self.assertEqual(
                    result["fallback_validation"]["reason"], "unsupported_course"
                )
                self.assertIsNone(result["query"])

    def test_contextual_predictions_need_an_actual_reference_of_the_right_type(self):
        for text, qtype in [
            ("NLP có bao nhiêu chương?", "COURSE_CHAPTER_COUNT"),
            ("CFG có nằm trong chương 3 không?", "CONTENT_CHAPTER"),
            ("Chương này cần nộp file gì?", "PART_OUTPUT"),
        ]:
            with self.subTest(text=text):
                result = self.forced(qtype).process(text)
                self.assertEqual(
                    result["fallback_validation"]["reason"], "missing_reference"
                )
                self.assertFalse(result["statistical_used"])

    def test_supported_reference_still_resolves_in_the_session(self):
        session = DialogueSession(self.forced("COURSE_CHAPTER_COUNT"))
        # Seed using the same KB and a symbolic turn, before forcing no-parse handling.
        session.assistant = self.assistant
        session.process("Môn NLP có mấy tín chỉ?")
        session.assistant = self.forced("COURSE_CHAPTER_COUNT")
        result = session.process("Bạn cho biết môn này có bao nhiêu chương vậy?")
        self.assertEqual(result["status"], "ok")
        self.assertTrue(result["statistical_used"])
        self.assertEqual(result["semantic"]["arguments"], {"course_id": "CO3085"})

    def test_extractor_cannot_manufacture_a_context_reference(self):
        extractor = EntityExtractor(self.lexicon)
        self.assertIsNone(
            extractor.extract(
                "Môn Cơ sở dữ liệu có bao nhiêu chương?", {"context_ref": "ENTITY"}
            )
        )
        self.assertEqual(
            extractor.extract("Còn chương sau?", {"context_ref": "ENTITY"}),
            {"context_ref": "CONTEXT_REF"},
        )

    def test_entity_words_are_not_question_focus_evidence(self):
        self.assertEqual(
            self.policy.arguments_rejection(
                "Natural language processing with python?",
                "RESOURCE_YEAR",
                {"resource_id": "REFERENCE_2"},
            ),
            "missing_qtype_evidence",
        )
        self.assertIsNone(
            self.policy.arguments_rejection(
                "Natural language processing with python xuất bản năm nào?",
                "RESOURCE_YEAR",
                {"resource_id": "REFERENCE_2"},
            )
        )

    def test_confidence_must_be_valid_and_respect_the_model_threshold(self):
        for confidence, reason in [
            (float("nan"), "invalid_confidence"),
            (float("inf"), "invalid_confidence"),
            (1.1, "invalid_confidence"),
            (True, "invalid_confidence"),
            (0.01, "low_confidence"),
        ]:
            with self.subTest(confidence=confidence):
                result = self.forced("CREDITS", confidence).process(
                    "NLP có mấy tín chỉ?"
                )
                self.assertEqual(result["fallback_validation"]["reason"], reason)
                self.assertFalse(result["statistical_used"])
                json.dumps(result, allow_nan=False)

    def test_cue_accent_tolerance_does_not_guess_entity_aliases(self):
        good = self.forced("CREDITS").process("NLP có mấy tín chĩ?")
        self.assertTrue(good["statistical_used"])
        bad = self.forced("CREDITS").process("nlpz có mấy tín chĩ?")
        self.assertEqual(bad["fallback_validation"]["reason"], "missing_entities")

    def test_actual_model_keeps_known_valid_paraphrases_and_missing_information(self):
        for text, qtype, status in [
            ("Bạn cho mình hỏi số tín chỉ của NLP với", "CREDITS", "ok"),
            ("NLP có mấy tín chĩ?", "CREDITS", "ok"),
            (
                "Bạn biết tác giả của introduction to natural language processing không?",
                "RESOURCE_AUTHOR",
                "ok",
            ),
            (
                "Cho tôi hỏi hạn nộp của BTL là lúc nào vậy?",
                "DEADLINE",
                "missing_information",
            ),
            ("Mình phải nộp BTL vào thời điểm nào?", "DEADLINE", "missing_information"),
            ("Cho mình biết ai dạy môn NLP với", "INSTRUCTOR", "missing_information"),
        ]:
            with self.subTest(text=text):
                result = self.assistant.process(text)
                self.assertTrue(result["statistical_used"])
                self.assertEqual(result["status"], status)
                self.assertEqual(result["semantic"]["qtype"], qtype)

    def test_rejected_requests_do_not_replace_dialogue_context(self):
        for text in (
            "Học phí môn NLP là bao nhiêu?",
            "Môn Cơ sở dữ liệu có bao nhiêu chương?",
            "Bài tập lớn môn Toán yêu cầu gì?",
            "Thời tiết hôm nay thế nào?",
        ):
            with self.subTest(text=text):
                session = DialogueSession(self.assistant)
                session.process("Bài tập lớn có phần parser không?")
                result = session.process(text)
                self.assertEqual(result["status"], "parse_failed")
                self.assertEqual(result["context_after"], result["context_before"])
                result = session.process("Phần này cần xuất file gì?")
                self.assertEqual(result["status"], "ok")
                self.assertEqual(result["semantic"]["arguments"]["part_id"], "PART_I")
                self.assertEqual(result["context_used"]["source_turn"], 1)

    def test_symbolic_parses_do_not_call_the_statistical_validator(self):
        policy = self.assistant.fallback_policy
        self.assistant.fallback_policy = Mock()
        try:
            result = self.assistant.process("Môn NLP có mấy tín chỉ?")
            self.assertEqual(result["status"], "ok")
            self.assertIsNone(result["fallback_validation"])
            self.assistant.fallback_policy.prediction_rejection.assert_not_called()
        finally:
            self.assistant.fallback_policy = policy
