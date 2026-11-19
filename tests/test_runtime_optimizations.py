"""Performance boundaries with behavior checks instead of machine-dependent time limits."""

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from nltk.grammar import FeatureGrammar

from src.application.pipeline import CourseAssistant
from src.config import ROOT
from src.lexical import Lexicon
from src.parsing import Parser, load_grammar
from src.preprocessing import normalize, tokenize
from src.statistical_processing.entity_extractor import EntityExtractor


class RuntimeOptimizationTests(unittest.TestCase):
    def test_help_does_not_import_the_processing_graph(self):
        script = """
import sys
sys.modules['src.application.runner'] = None
from src.main import main
sys.argv=['course-assistant','--help']
main()
"""
        result = subprocess.run(
            [sys.executable, "-c", script],
            check=False,
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("evaluate", result.stdout)

    def test_grammar_is_compiled_once_and_still_parses(self):
        with patch(
            "src.parsing.grammar_loader.FeatureGrammar.fromstring",
            wraps=FeatureGrammar.fromstring,
        ) as compiler:
            grammar = load_grammar()
        self.assertEqual(compiler.call_count, 1)
        self.assertTrue(
            Parser(grammar).parse_all(tokenize(normalize("Môn NLP có mấy tín chỉ?")))
        )

    def test_grammar_only_does_not_deserialize_a_model(self):
        with patch("src.application.pipeline._load_statistical_recognizer") as loader:
            assistant = CourseAssistant(use_statistical=False)
        loader.assert_not_called()
        record = assistant.process("Bạn cho mình hỏi số tín chỉ của NLP với")
        self.assertEqual(record["status"], "parse_failed")
        self.assertFalse(record["statistical_attempted"])

    def test_entity_index_keeps_longest_match_and_mention_order(self):
        lexicon = Lexicon(
            {
                "entity_entries": [
                    {
                        "category": "TOPIC",
                        "canonical_id": "SHORT",
                        "entity_type": "topic",
                        "aliases": ["natural language"],
                    },
                    {
                        "category": "TOPIC",
                        "canonical_id": "LONG",
                        "entity_type": "topic",
                        "aliases": ["natural language processing"],
                    },
                    {
                        "category": "TOPIC",
                        "canonical_id": "CFG",
                        "entity_type": "topic",
                        "aliases": ["cfg"],
                    },
                ]
            }
        )
        extractor = EntityExtractor(lexicon)
        self.assertEqual(
            extractor.extract("natural language processing", {"topic_id": "ENTITY"}),
            {"topic_id": "LONG"},
        )
        self.assertEqual(
            extractor.extract(
                "cfg và natural language processing",
                {"topic_ids": ("ENTITY", "TARGET")},
            ),
            {"topic_ids": ["CFG", "LONG"]},
        )
        self.assertIsNone(extractor.extract("unknown topic", {"topic_id": "ENTITY"}))

    def test_ambiguous_alias_is_neither_one_entity_nor_two_conjoined_entities(self):
        extractor = EntityExtractor(
            Lexicon(
                {
                    "entity_entries": [
                        {
                            "category": "TOPIC",
                            "canonical_id": "A",
                            "entity_type": "topic",
                            "aliases": ["ambiguous"],
                        },
                        {
                            "category": "TOPIC",
                            "canonical_id": "B",
                            "entity_type": "topic",
                            "aliases": ["ambiguous"],
                        },
                    ]
                }
            )
        )
        self.assertIsNone(extractor.extract("ambiguous", {"topic_id": "ENTITY"}))
        self.assertIsNone(
            extractor.extract("ambiguous", {"topic_ids": ("ENTITY", "TARGET")})
        )

    def test_inference_does_not_load_pyplot_and_evaluation_can_still_plot(self):
        script = """
import sys
sys.modules['matplotlib.pyplot'] = None
from src.statistical_processing.intent_recognizer import QTypeRecognizer
rec=QTypeRecognizer(['CREDITS','DEADLINE'])
rec.train(['credits please','credits course','deadline please','deadline assignment'],['CREDITS','CREDITS','DEADLINE','DEADLINE'])
assert rec.predict('credits course') == 'CREDITS'
"""
        result = subprocess.run(
            [sys.executable, "-c", script],
            check=False,
            cwd=ROOT,
            env=os.environ.copy(),
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        from src.statistical_processing.intent_recognizer import QTypeRecognizer

        rec = QTypeRecognizer(["CREDITS", "DEADLINE"])
        rec.train(
            [
                "credits please",
                "credits course",
                "deadline please",
                "deadline assignment",
            ],
            ["CREDITS", "CREDITS", "DEADLINE", "DEADLINE"],
        )
        with tempfile.TemporaryDirectory() as directory:
            result = rec.eval(
                ["credits course", "deadline assignment"],
                ["CREDITS", "DEADLINE"],
                eval_path=directory,
            )
            self.assertEqual(result["accuracy"], 1)
            self.assertTrue(
                (Path(directory) / "confusion_matrix.png")
                .read_bytes()
                .startswith(b"\x89PNG")
            )
