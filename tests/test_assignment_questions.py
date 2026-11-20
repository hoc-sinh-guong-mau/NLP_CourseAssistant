"""Assignment task questions must not bind an assignment ID to a course slot."""

import tempfile
import unittest
from pathlib import Path

from src.application.pipeline import CourseAssistant
from src.preprocessing import normalize, tokenize
from src.retrieval.sqlite import SQLiteKnowledgeBase, build_sqlite


class AssignmentQuestionTests(unittest.TestCase):
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

    def assert_request(self, text, qtype, arguments, *, status="ok"):
        assistant = self.assistant
        trees = assistant.parser.parse_all(tokenize(normalize(text)))
        self.assertTrue(trees, text)
        frames = [assistant.semantic.interpret(tree) for tree in trees]
        self.assertEqual(len({frame.canonical_key() for frame in frames}), 1, text)
        self.assertEqual(
            frames[0].to_dict(),
            {
                "predicate": "GET_ASSIGNMENT",
                "qtype": qtype,
                "arguments": arguments,
            },
        )
        result = assistant.process(text)
        self.assertEqual(result["status"], status, text)
        self.assertFalse(result["statistical_attempted"])
        return result

    def test_task_verbs_generalize_across_assignment_aliases(self):
        for alias in ("Bài tập lớn", "BTL", "Bài tập 1", "BTL01", "assignment 1"):
            for phrase in (
                "làm gì",
                "cần làm những gì",
                "phải thực hiện gì",
                "cần hoàn thành những gì",
                "yêu cầu xây dựng những gì",
                "yêu cầu làm gì",
                "có yêu cầu gì",
            ):
                with self.subTest(alias=alias, phrase=phrase):
                    result = self.assert_request(
                        f"{alias} {phrase}?", "REQUIREMENTS", {"assignment_id": "BTL01"}
                    )
                    self.assertEqual(result["query"]["collection"], "assignment_parts")
                    self.assertEqual(
                        result["query"]["filters"], {"assignment_id": "BTL01"}
                    )

    def test_task_subjects_and_context_phrases(self):
        for text in (
            "Tôi cần làm gì cho bài tập lớn?",
            "Mình phải làm những gì trong BTL?",
            "Cần thực hiện gì cho bài tập 1?",
            "BTL nhóm tôi cần làm gì?",
            "Trong bài tập lớn tôi cần làm những gì?",
            "Cho tôi biết BTL làm gì nhé",
        ):
            with self.subTest(text=text):
                self.assert_request(text, "REQUIREMENTS", {"assignment_id": "BTL01"})

    def test_submission_questions_ask_for_outputs(self):
        for text in (
            "Bài tập lớn nộp gì?",
            "BTL cần nộp những gì?",
            "BTL phải nộp file gì?",
            "Bài tập lớn yêu cầu nộp những sản phẩm nào?",
            "BTL cần xuất các file nào?",
            "Tôi cần nộp gì cho BTL?",
        ):
            with self.subTest(text=text):
                result = self.assert_request(
                    text, "OUTPUTS", {"assignment_id": "BTL01"}
                )
                self.assertEqual(result["query"]["collection"], "assignments")
                self.assertEqual(result["query"]["filters"], {"id": "BTL01"})

    def test_goal_and_part_questions_keep_their_own_meaning(self):
        for text, qtype, arguments, status in (
            ("BTL để làm gì?", "GOAL", {"assignment_id": "BTL01"}, "ok"),
            ("Mục tiêu của BTL là gì?", "GOAL", {"assignment_id": "BTL01"}, "ok"),
            (
                "Phần I của BTL cần làm gì?",
                "PART_REQUIREMENTS",
                {"assignment_id": "BTL01", "part_id": "PART_I"},
                "ok",
            ),
            (
                "Phần II của BTL cần nộp file gì?",
                "PART_OUTPUTS",
                {"assignment_id": "BTL01", "part_id": "PART_II"},
                "missing_information",
            ),
        ):
            with self.subTest(text=text):
                self.assert_request(text, qtype, arguments, status=status)

    def test_assignment_lists_bind_the_course_not_the_assignment(self):
        for text in (
            "Tôi cần hoàn thành những bài tập nào?",
            "Mình cần làm các bài tập gì?",
            "Hãy liệt kê những bài tập nào",
            "Môn NLP có những bài tập nào?",
            "CO3085 có các bài tập gì?",
            "Môn học có những bài tập nào?",
            "Những bài tập nào của môn NLP?",
            "Tôi cần nộp những bài tập nào của CO3085?",
            "Hãy liệt kê các bài tập",
            "Liệt kê các bài tập của môn NLP",
        ):
            with self.subTest(text=text):
                result = self.assert_request(
                    text, "ASSIGNMENT_LIST", {"course_id": "CO3085"}
                )
                self.assertEqual(result["query"]["filters"], {"course_id": "CO3085"})

    def test_generic_actions_and_wrong_entity_types_are_not_lists(self):
        for text in (
            "Tôi cần làm gì?",
            "Mình cần nộp gì?",
            "Bài tập lớn có những bài tập nào?",
            "Môn chưa biết có những bài tập nào?",
            "Thời tiết hôm nay làm gì?",
        ):
            with self.subTest(text=text):
                result = self.assistant.process(text)
                self.assertEqual(result["status"], "parse_failed")
                self.assertIsNone(result["query"])
