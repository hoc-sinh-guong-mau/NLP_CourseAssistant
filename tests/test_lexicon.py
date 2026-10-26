import tempfile
import unittest
from pathlib import Path

from src.config import GRAMMAR_PATH, LEXICON_DIR
from src.lexical import EntityResolver, Lexicon
from src.parsing import Parser
from src.parsing.grammar_loader import load_syntax
from src.preprocessing import normalize, tokenize
from src.semantic import SemanticInterpreter
from src.retrieval import KnowledgeBase
from src.application.pipeline import CourseAssistant


class LexiconTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.semantic = SemanticInterpreter()
        cls.lexicon = Lexicon.load(LEXICON_DIR)
        cls.parser = Parser(cls.lexicon.compile(load_syntax()))

    def test_week_aliases_have_same_semantics(self):
        for alias in ("tuần ba", "tuần 3", "week 3"):
            with self.subTest(alias=alias):
                trees = self.parser.parse_all(tokenize(normalize(f"{alias} học gì?")))
                self.assertTrue(trees)
                for tree in trees:
                    frame = self.semantic.interpret(tree)
                    self.assertEqual(frame.predicate, "GET_SCHEDULE")
                    self.assertEqual(frame.arguments, {"week_id": "WEEK_03"})

    def test_original_entity_aliases(self):
        resolver = EntityResolver(self.lexicon)
        for alias, category, expected in [
            ("NLP", "COURSE", "CO3085"),
            ("context-free grammar", "TOPIC", "CFG"),
            ("btl", "ASSIGNMENT_NAME", "BTL01"),
        ]:
            self.assertEqual([e.canonical_id for e in resolver.lookup_alias(alias, category)], [expected])
        self.assertEqual(resolver.lookup_alias("tuần 99"), [])

    def test_assignment_one_is_alias_of_project(self):
        resolver = EntityResolver(self.lexicon)
        for alias in ("bài tập 1", "assignment 1", "bài tập lớn"):
            with self.subTest(alias=alias):
                self.assertEqual(
                    [entry.canonical_id for entry in resolver.lookup_alias(alias, "ASSIGNMENT_NAME")],
                    ["BTL01"],
                )
                trees = self.parser.parse_all(tokenize(normalize(f"Khi nào nộp {alias}?")))
                self.assertTrue(trees)
                self.assertTrue(all(self.semantic.interpret(tree).arguments == {"assignment_id": "BTL01"}
                                    for tree in trees))

    def test_ambiguous_alias_preserves_both_entities(self):
        lexicon = Lexicon({"entity_entries": [
            {"category": "TOPIC", "canonical_id": entity, "entity_type": "topic", "aliases": ["trùng"]}
            for entity in ("A", "B")
        ]})
        resolver = EntityResolver(lexicon)
        self.assertEqual(len(resolver.lookup_alias("TRÙNG")), 2)
        self.assertEqual(resolver.collisions(), {("TOPIC", "trùng"): ["A", "B"]})
        grammar = lexicon.compile("% start S\nS[ENTITY=?e] -> TOPIC[ENTITY=?e]")
        trees = Parser(grammar).parse_all(["trùng"])
        self.assertEqual({t.label()["ENTITY"] for t in trees}, {"A", "B"})

    def test_invalid_schema_is_rejected(self):
        for data in ([], {"unknown": []}, {"entity_entries": [{"category": "WEEK", "aliases": ["tuần"]}]},
                     {"lexical_entries": [{"category": "WHAT", "aliases": ["???"]}]}):
            with self.subTest(data=data), self.assertRaises(ValueError):
                Lexicon(data)

    def test_cross_file_duplicates_rejected(self):
        text = "lexical_entries:\n- category: WHAT\n  aliases: [gì]\n"
        with tempfile.TemporaryDirectory() as directory:
            for name in ("a.yaml", "b.yaml"):
                Path(directory, name).write_text(text, encoding="utf-8")
            with self.assertRaises(ValueError):
                Lexicon.load(Path(directory))

    def test_yaml_uses_safe_loader(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory, "bad.yaml")
            path.write_text("!!python/object:builtins.object {}", encoding="utf-8")
            with self.assertRaises(ValueError):
                Lexicon.load(path)

    def test_kb_and_pipeline_after_migration(self):
        kb = KnowledgeBase()
        self.assertEqual(set(kb.collections), {"course", "schedule", "assignments"})
        self.assertEqual(len(kb.collections["schedule"]), 15)
        record = CourseAssistant().process("Deadline bài tập lớn là khi nào?")
        self.assertEqual(record["status"], "ok")
        self.assertEqual(record["query"]["filters"], {"id": "BTL01"})
        self.assertEqual(CourseAssistant().process("tuần ba học gì?")["status"], "unsupported_query")

    def test_duplicate_yaml_keys_rejected(self):
        texts = [
            "lexical_entries: []\nlexical_entries: []\n",
            "lexical_entries:\n- category: WHAT\n  category: WHEN\n  aliases: [gì]\n",
        ]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory, "duplicate.yaml")
            for text in texts:
                path.write_text(text, encoding="utf-8")
                with self.subTest(text=text), self.assertRaisesRegex(ValueError, "Duplicate YAML key"):
                    Lexicon.load(path)

    def test_schema_typos_and_unrepresentable_alias_rejected(self):
        for data in (
            {},
            {"lexical_entries": [{"category": "WHAT", "aliases": ["gì"], "alias": ["nào"]}]},
            {"entity_entries": [{"category": "WEEK", "entity_type": " ", "canonical_id": "WEEK_03", "aliases": ["ba"]}]},
            {"entity_entries": [{"category": "WEEK", "entity_type": "week", "canonical_id": " WEEK_03 ", "aliases": ["ba"]}]},
            {"lexical_entries": [{"category": "WORD", "aliases": ["a" + chr(92) + "b"]}]},
        ):
            with self.subTest(data=data), self.assertRaises(ValueError):
                Lexicon(data)

    def test_alias_normalization_deduplication_and_text_round_trip(self):
        aliases = [" TUẦN   BA??? ", "tuần ba", "o'reilly", 'say "hello"']
        lexicon = Lexicon({"lexical_entries": [{"category": "WORD", "aliases": aliases}]})
        self.assertEqual(lexicon.entries[0].aliases, ("tuần ba", "o'reilly", 'say "hello"'))
        grammar = lexicon.compile("% start S\nS -> WORD")
        self.assertEqual(grammar.productions()[1:], list(lexicon.productions()))

    def test_empty_directory_and_empty_yaml_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            with self.assertRaises(ValueError):
                Lexicon.load(path)
            (path / "empty.yaml").write_text("", encoding="utf-8")
            with self.assertRaises(ValueError):
                Lexicon.load(path)
