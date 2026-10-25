import unittest

from src.preprocessing.preprocessor import normalize, tokenize


class TokenizerTests(unittest.TestCase):
    def test_grammar_terminals(self):
        self.assertEqual(
            tokenize("tuần ba học nội dung gì"),
            ["tuần", "ba", "học", "nội", "dung", "gì"],
        )
        self.assertEqual(
            tokenize("lo2.5 llm/rag context-free bài tập lớn"),
            ["lo2.5", "llm/rag", "context-free", "bài", "tập", "lớn"],
        )

    def test_normalize_then_tokenize(self):
        self.assertEqual(
            tokenize(normalize(" L.O.2.5\tLLM/RAG CONTEXT-FREE??? ")),
            ["lo2.5", "llm/rag", "context-free"],
        )

    def test_empty_input(self):
        self.assertEqual(tokenize(normalize("?!")), [])

    def test_internal_punctuation_is_preserved(self):
        self.assertEqual(tokenize(normalize("cfg, parsing")), ["cfg,", "parsing"])
