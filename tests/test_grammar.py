import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from nltk.featstruct import TYPE
from nltk.grammar import FeatureGrammar

from src.artifacts.exporter import export_grammar
from src.parsing.generator import generate_sentences
from src.parsing import Parser, grammar_text, validate_grammar
from src.preprocessing import normalize, tokenize


class GrammarTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = grammar_text()
        cls.grammar = validate_grammar(cls.text)
        cls.parser = Parser(cls.grammar)

    def test_complete_grammar_covers_query_groups(self):
        cases = [
            ("Môn NLP có mấy tín chỉ?", "GET_COURSE_INFO", "CO3085", "CREDITS"),
            ("Tuần ba học gì?", "GET_SCHEDULE", "WEEK_03", "WEEK_CONTENT"),
            ("Chương nào nói về CFG?", "GET_TOPIC", "CFG", "FIND_CHAPTER_BY_TOPIC"),
            ("Bài tập lớn nhóm mấy người?", "GET_ASSIGNMENT", "BTL01", "TEAM_SIZE"),
            ("Deadline btl là khi nào?", "GET_DEADLINE", "BTL01", "DEADLINE"),
            ("Tài liệu nào nói về CFG?", "GET_RESOURCE", "CFG", "RESOURCE_BY_TOPIC"),
            ("Giảng viên môn NLP là ai?", "GET_INSTRUCTOR", "CO3085", "INSTRUCTOR"),
            ("Có được dùng AI không?", "GET_RULE", "AI_USAGE", "PERMISSION"),
            ("L.O.2.5 là gì?", "GET_LO", "LO2.5", "LO_INFO"),
            ("Còn chương sau?", "CONTEXT_DEPENDENT", "CONTEXT_REF", "NEXT_CHAPTER"),
            ("Nội dung này nằm ở chương nào?", "CONTEXT_DEPENDENT", "CONTEXT_REF", "CONTENT_CHAPTER"),
            ("Tôi cần hoàn thành những bài tập nào?", "GET_ASSIGNMENT", "CO3085", "ASSIGNMENT_LIST"),
        ]
        for text, intent, entity, qtype in cases:
            with self.subTest(text=text):
                trees = self.parser.parse_all(tokenize(normalize(text)))
                self.assertTrue(trees)
                for tree in trees:
                    self.assertEqual(tree.label()["INTENT"], intent)
                    self.assertEqual(tree.label()["ENTITY"], entity)
                    self.assertEqual(tree.label()["QTYPE"], qtype)

    def test_rejects_unknown_and_invalid_word_order(self):
        for text in ("tuần 99 học gì", "gì học tuần ba", "", "thời tiết hôm nay"):
            with self.subTest(text=text):
                self.assertEqual(self.parser.parse_all(tokenize(text)), [])

    def test_target_feature_survives_unification(self):
        trees = self.parser.parse_all(tokenize("chương 3 có cfg không"))
        self.assertTrue(trees)
        self.assertTrue(all(t.label()["TARGET"] == "CFG" for t in trees))

    def test_export_round_trip_and_determinism(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory, "output", "grammar.txt")
            export_grammar(path)
            first = path.read_text(encoding="utf-8")
            loaded = FeatureGrammar.fromstring(first)
            self.assertEqual(loaded.start()[TYPE], "S")
            self.assertEqual(loaded.productions(), self.grammar.productions())
            self.assertTrue(Parser(loaded).parse_all(["week", "3", "học", "gì"]))
            export_grammar(path)
            self.assertEqual(first, path.read_text(encoding="utf-8"))

    def test_undefined_category_and_start_rejected(self):
        for text in ("% start S\nS -> MISSING", "% start UNKNOWN\nS -> 'x'"):
            with self.subTest(text=text), self.assertRaises(ValueError):
                validate_grammar(text)

    def test_invalid_input_does_not_overwrite_export(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory, "bad.fcfg")
            source.write_text("% start S\nS -> MISSING", encoding="utf-8")
            output = Path(directory, "grammar.txt")
            output.write_text("previous result", encoding="utf-8")
            with patch("src.parsing.grammar_loader.GRAMMAR_PATH", source), self.assertRaises(ValueError):
                export_grammar(output)
            self.assertEqual(output.read_text(encoding="utf-8"), "previous result")

    def test_generated_samples_pass_feature_parser(self):
        samples = generate_sentences(20)
        self.assertTrue(samples)
        self.assertLessEqual(len(samples), 20)
        self.assertEqual(len(samples), len(set(samples)))
        for sentence in samples:
            self.assertTrue(self.parser.parse_all(tokenize(sentence)), sentence)
