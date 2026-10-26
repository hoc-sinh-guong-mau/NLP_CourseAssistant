import json
import tempfile
import unittest
from pathlib import Path

from nltk.grammar import FeatureGrammar

from src.application.pipeline import CourseAssistant
from src.artifacts.exporter import export_records
from src.parsing import Parser
from src.semantic import SemanticFrame, extract


class IntentEntityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.assistant = CourseAssistant()

    def test_aliases_produce_same_intent_and_entities(self):
        groups = [
            ([f'Khi nào nộp {alias}?' for alias in ('bài tập lớn', 'bài tập 1', 'btl')],
             {'intent': 'GET_DEADLINE', 'qtype': 'DEADLINE', 'entities': {'assignment_id': 'BTL01'}}),
            ([f'{alias} học gì?' for alias in ('tuần ba', 'tuần 3', 'week 3')],
             {'intent': 'GET_SCHEDULE', 'qtype': 'WEEK_CONTENT', 'entities': {'week_id': 'WEEK_03'}}),
        ]
        for texts, expected in groups:
            for text in texts:
                with self.subTest(text=text):
                    self.assertEqual(self.assistant.process(text)['intent_entity'], expected)

    def test_entity_roles_lists_and_qtype_are_preserved(self):
        cases = [
            ('Chương 3 có CFG không?', 'GET_TOPIC', 'CHAPTER_HAS_TOPIC',
             {'chapter_id': 'CH03', 'topic_id': 'CFG'}),
            ('CFG và parsing nằm ở tuần nào?', 'GET_SCHEDULE', 'TOPICS_WEEK',
             {'topic_ids': ['CFG', 'PARSING']}),
            ('Tuần 3 học chương nào?', 'GET_SCHEDULE', 'WEEK_CHAPTER', {'week_id': 'WEEK_03'}),
        ]
        for text, intent, qtype, entities in cases:
            with self.subTest(text=text):
                self.assertEqual(self.assistant.process(text)['intent_entity'],
                                 {'intent': intent, 'qtype': qtype, 'entities': entities})

    def test_extract_does_not_share_mutable_slots(self):
        frame = SemanticFrame('GET_SCHEDULE', {'topic_ids': ['CFG', 'PARSING']}, 'TOPICS_WEEK')
        result = extract(frame)
        result['entities']['topic_ids'].append('PCFG')
        self.assertEqual(frame.arguments, {'topic_ids': ['CFG', 'PARSING']})
        frame.arguments['topic_ids'].append('LEXICON')
        self.assertEqual(result['entities']['topic_ids'], ['CFG', 'PARSING', 'PCFG'])

    def test_context_remains_unresolved(self):
        record = self.assistant.process('Còn chương sau?')
        self.assertEqual(record['status'], 'needs_context')
        self.assertEqual(record['intent_entity']['entities'], {'context_ref': 'CONTEXT_REF'})

    def test_failures_have_no_guessed_intent_or_entity(self):
        self.assertIsNone(self.assistant.process('Thời tiết hôm nay thế nào?')['intent_entity'])
        grammar = FeatureGrammar.fromstring(
            "% start S\nS[INTENT='UNKNOWN', QTYPE='UNKNOWN', ENTITY='X'] -> 'x'"
        )
        record = CourseAssistant(parser=Parser(grammar)).process('x')
        self.assertEqual(record['status'], 'unsupported_semantic')
        self.assertIsNone(record['intent_entity'])

    def test_ambiguous_meanings_are_not_collapsed_into_one_intent_entity(self):
        grammar = FeatureGrammar.fromstring(
            "% start S\n"
            "S[INTENT='GET_DEADLINE', QTYPE='DEADLINE', ENTITY=?e] -> X[ENTITY=?e]\n"
            "X[ENTITY='A'] -> 'x'\nX[ENTITY='B'] -> 'x'"
        )
        record = CourseAssistant(parser=Parser(grammar)).process('x')
        self.assertEqual(record['status'], 'ambiguous')
        self.assertIsNone(record['intent_entity'])
        self.assertEqual({f['arguments']['assignment_id'] for f in record['alternatives']}, {'A', 'B'})

    def test_export_preserves_record_order_and_null(self):
        records = [self.assistant.process(text) for text in (
            'Môn NLP có mấy tín chỉ?', 'Thời tiết hôm nay thế nào?', 'Khi nào nộp bài tập 1?',
        )]
        with tempfile.TemporaryDirectory() as directory:
            export_records(records, output_dir=directory)
            root = Path(directory)
            intents = [json.loads(line) for line in (root / 'intent-entity.txt').read_text(encoding='utf-8').splitlines()]
            semantics = [json.loads(line) for line in (root / 'semantic.txt').read_text(encoding='utf-8').splitlines()]
            self.assertEqual(intents, [r['intent_entity'] for r in records])
            self.assertIsNone(intents[1])
            for semantic, intent in zip(semantics, intents):
                if semantic is not None:
                    self.assertEqual(intent['intent'], semantic['predicate'])
                    self.assertEqual(intent['qtype'], semantic['qtype'])
                    self.assertEqual(intent['entities'], semantic['arguments'])
