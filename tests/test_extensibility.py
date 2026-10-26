"""Extension contracts: registries, injected stages and modular data loading."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from src.application.pipeline import CourseAssistant
from src.generation.answer import AnswerGenerator, UnsupportedAnswerError
from src.parsing.grammar_loader import load_syntax, validate_grammar
from src.parsing.parser import Parser
from src.retrieval.knowledge_base import KnowledgeBase
from src.retrieval.query_builder import QueryBuilder, QuerySpec, UnsupportedQueryError
from src.semantic import SemanticFrame


class ExtensionTests(unittest.TestCase):
    def test_custom_query_and_answer_registries_are_isolated(self):
        frame = SemanticFrame('GET_COURSE_INFO', {'course_id':'CO3085'}, 'CREDITS')
        key = ('GET_COURSE_INFO','CREDITS')
        builder = QueryBuilder({key: QuerySpec('course', (('id','course_id'),), ('credits',))})
        self.assertEqual(builder.build(frame), {
            'collection':'course', 'filters':{'id':'CO3085'}, 'select':['credits'],
        })
        renderer = AnswerGenerator({key: lambda rows: ('ok', str(rows[0]['credits']))})
        self.assertEqual(renderer.render(frame, [{'credits':3}]), ('ok','3'))
        with self.assertRaises(UnsupportedQueryError):
            QueryBuilder().build(frame)
        with self.assertRaises(UnsupportedAnswerError):
            AnswerGenerator().render(frame, [])

    def test_new_kb_collection_discovered_and_duplicate_ids_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory,'resources.json')
            path.write_text(json.dumps([{'id':'R1','title':'Book'}]), encoding='utf-8')
            kb = KnowledgeBase(Path(directory))
            self.assertEqual(kb.execute({'collection':'resources','filters':{'id':'R1'}})[0]['title'],'Book')
            path.write_text(json.dumps([{'id':'R1'},{'id':'R1'}]), encoding='utf-8')
            with self.assertRaises(ValueError):
                KnowledgeBase(Path(directory))

    def test_modular_grammar_assembly_and_single_start_directive(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            entry = root/'syntax.fcfg'
            entry.write_text('% start S\nS -> QUESTION', encoding='utf-8')
            rules = root/'rules'
            rules.mkdir()
            fragment = rules/'questions.fcfg'
            fragment.write_text("QUESTION -> 'hello'", encoding='utf-8')
            self.assertTrue(Parser(validate_grammar(load_syntax(entry))).parse_all(['hello']))
            fragment.write_text("% start QUESTION\nQUESTION -> 'hello'", encoding='utf-8')
            with self.assertRaises(ValueError):
                load_syntax(entry)

    def test_pipeline_injected_query_failure_is_not_hidden(self):
        query_builder = Mock()
        query_builder.build.side_effect = ValueError('implementation error')
        assistant = CourseAssistant(query_builder=query_builder)
        with self.assertRaisesRegex(ValueError,'implementation error'):
            assistant.process('Deadline btl là khi nào?')
        query_builder.build.side_effect = UnsupportedQueryError('not implemented')
        self.assertEqual(assistant.process('Deadline btl là khi nào?')['status'],'unsupported_query')

    def test_missing_slot_is_not_an_unsupported_query(self):
        frame = SemanticFrame('GET_DEADLINE', {}, 'DEADLINE')
        with self.assertRaises(KeyError):
            QueryBuilder().build(frame)
