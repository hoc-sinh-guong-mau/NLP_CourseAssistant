"""End-to-end requirements from the assignment, including grounded non-answers."""

import tempfile
import unittest
from pathlib import Path

from src.application.pipeline import CourseAssistant
from src.config import LEXICON_DIR
from src.dialogue import DialogueSession
from src.lexical import Lexicon
from src.retrieval.normalization import build_collections
from src.retrieval.normalization.builder import match_entities
from src.retrieval.sqlite import SQLiteKnowledgeBase, build_sqlite


class CourseGoalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = tempfile.TemporaryDirectory()
        database = Path(cls.directory.name) / "kb.sqlite3"
        build_sqlite(database=database)
        cls.assistant = CourseAssistant(
            kb=SQLiteKnowledgeBase(database), use_statistical=False
        )

    @classmethod
    def tearDownClass(cls):
        cls.directory.cleanup()

    def test_source_method_mentions_keep_the_generic_topic_and_specific_ids(self):
        topics = [
            entry
            for entry in Lexicon.load(LEXICON_DIR).entries
            if entry.category == "TOPIC"
        ]
        evidence = match_entities("top-down parsing; bottom-up chart parsing", topics)
        self.assertEqual(
            set(evidence), {"PARSING", "TOP_DOWN_PARSING", "BOTTOM_UP_CHART_PARSING"}
        )
        self.assertEqual(evidence["PARSING"], ["parsing"])
        # Do not infer arbitrary parent topics just because their aliases overlap.
        self.assertEqual(
            set(match_entities("probabilistic context-free grammar", topics)), {"PCFG"}
        )
        self.assertNotIn("PARSING", match_entities("unification grammar", topics))

    def test_combined_topic_schedule_question_returns_source_backed_week(self):
        result = self.assistant.process("Phần CFG và Parsing nằm ở tuần nào?")
        self.assertEqual(result["status"], "ok")
        self.assertEqual(
            result["semantic"]["arguments"], {"topic_ids": ["CFG", "PARSING"]}
        )
        self.assertEqual([row["week"] for row in result["result"]], [3])
        self.assertIn("3", result["answer"])
        self.assertIn("schedule.txt", result["answer"])
        self.assertFalse(result["statistical_used"])

    def test_schedule_links_retain_source_evidence_without_new_records(self):
        data = build_collections()
        self.assertEqual((len(data), sum(map(len, data.values()))), (14, 118))
        week = next(row for row in data["schedule"] if row["id"] == "WEEK_03")
        self.assertIn("PARSING", week["topic_ids"])
        self.assertIn("TOP_DOWN_PARSING", week["topic_ids"])
        self.assertEqual(week["topic_evidence"]["PARSING"], ["parsing"])
        self.assertFalse(week["topic_links_complete"])

    def test_missing_facts_are_not_invented_to_answer_assignment_examples(self):
        for text in (
            "Deadline của bài tập lớn là khi nào?",
            "Tài liệu nào nói về CFG?",
            "Bài tập lớn có được sử dụng công cụ AI không?",
        ):
            with self.subTest(text=text):
                result = self.assistant.process(text)
                self.assertEqual(result["status"], "missing_information")
                self.assertIsNotNone(result["semantic"])
                self.assertIsNotNone(result["query"])

    def test_followup_uses_previous_week_and_honestly_reports_missing_resources(self):
        session = DialogueSession(self.assistant)
        session.process("Tuần 5 học những gì?")
        result = session.process("Tài liệu của phần này ở đâu?")
        self.assertEqual(result["context_used"]["source_turn"], 1)
        self.assertEqual(result["semantic"]["qtype"], "RESOURCE_BY_CHAPTER")
        self.assertEqual(result["status"], "missing_information")
        self.assertEqual(result["result"], [])
