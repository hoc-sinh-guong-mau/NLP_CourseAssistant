import unittest
import unicodedata

from src.preprocessing.preprocessor import normalize


class NormalizerTests(unittest.TestCase):
    def test_normalization_contract(self):
        cases = [
            ("  TUẦN   Ba   học  nội dung  gì???  ", "tuần ba học nội dung gì"),
            ("TUẦN\tba\n học\u00a0gì?!", "tuần ba học gì"),
            (unicodedata.normalize("NFD", "TUẦN BA"), "tuần ba"),
            ("L.O.2.5 là gì?", "lo2.5 là gì"),
            ("L.O.2.5...", "lo2.5"),
            ("L. O. 2.5 là gì ? !", "lo2.5 là gì"),
            ("lo2.5 llm/rag context-free.", "lo2.5 llm/rag context-free"),
            ("mục 2.5, ví dụ: a.b; cfg", "mục 2.5, ví dụ: a.b; cfg"),
            ("", ""),
            (" \t\n", ""),
            ("?!...", ""),
        ]
        for raw, expected in cases:
            with self.subTest(raw=raw):
                self.assertEqual(normalize(raw), expected)
                self.assertEqual(normalize(expected), expected)

    def test_normalize_keeps_original(self):
        original = " TUẦN Ba??? "
        self.assertEqual(normalize(original), "tuần ba")
        self.assertEqual(original, " TUẦN Ba??? ")

    def test_invalid_input(self):
        with self.assertRaises(TypeError):
            normalize(None)  # pyright: ignore[reportArgumentType]
