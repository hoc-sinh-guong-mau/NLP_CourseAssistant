"""Unified error contracts: stage attribution, causes and pipeline behavior."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from src.common import NLPError, StageExecutionError, run_stage
from src.lexical import Lexicon, LexiconError
from src.lexical.validation import LexiconError as ValidationLexiconError
from src.parsing import GrammarError, validate_grammar
from src.retrieval import KnowledgeBase, KnowledgeBaseError, UnsupportedQueryError
from src.application.pipeline import CourseAssistant


class ErrorTests(unittest.TestCase):
    def test_one_lexicon_error_class_and_file_context(self):
        self.assertIs(LexiconError, ValidationLexiconError)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory, 'bad.yaml')
            path.write_text('entity_entries:\n- category: WEEK\n', encoding='utf-8')
            with self.assertRaises(LexiconError) as caught:
                Lexicon.load(path)
            error = caught.exception
            self.assertEqual(error.stage, 'lexical')
            self.assertEqual(error.context['path'], str(path))
            self.assertIsInstance(error.__cause__, LexiconError)

    def test_missing_yaml_file_preserves_os_error(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(LexiconError) as caught:
                Lexicon.load(Path(directory, 'missing.yaml'))
            self.assertIsInstance(caught.exception.__cause__, FileNotFoundError)

    def test_invalid_grammar_preserves_original_syntax_error(self):
        with self.assertRaises(GrammarError) as caught:
            validate_grammar('this is not a grammar')
        self.assertEqual(caught.exception.stage, 'grammar')
        self.assertIsInstance(caught.exception.__cause__, ValueError)

    def test_invalid_json_has_kb_stage_and_path(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory, 'course.json')
            path.write_text('{', encoding='utf-8')
            with self.assertRaises(KnowledgeBaseError) as caught:
                KnowledgeBase(Path(directory))
            self.assertEqual(caught.exception.stage, 'knowledge_base')
            self.assertEqual(caught.exception.context['path'], str(path))
            self.assertIsNotNone(caught.exception.__cause__)

    def test_unexpected_errors_are_attributed_at_each_pipeline_stage(self):
        assistant = CourseAssistant()
        for component, method, stage in [
            ('parser','parse_all','parsing'), ('semantic','interpret','semantic'),
            ('query_builder','build','query'), ('kb','execute','knowledge_base'),
            ('answer_generator','render','generation'),
        ]:
            with self.subTest(stage=stage):
                original = getattr(assistant, component)
                injected = Mock()
                cause = RuntimeError('test failure')
                getattr(injected, method).side_effect = cause
                setattr(assistant, component, injected)
                try:
                    with self.assertRaises(StageExecutionError) as caught:
                        assistant.process('Deadline btl là khi nào?')
                    self.assertEqual(caught.exception.stage, stage)
                    self.assertIs(caught.exception.__cause__, cause)
                finally:
                    setattr(assistant, component, original)

    def test_expected_query_error_becomes_structured_trace(self):
        builder = Mock()
        builder.build.side_effect = UnsupportedQueryError('not implemented')
        result = CourseAssistant(query_builder=builder).process('Deadline btl là khi nào?')
        self.assertEqual(result['status'], 'unsupported_query')
        self.assertEqual(result['error']['stage'], 'query')
        self.assertEqual(result['error']['code'], 'QUERY_UNSUPPORTED')
        self.assertEqual(result['error']['type'], 'UnsupportedQueryError')

    def test_run_stage_preserves_domain_error_identity(self):
        error = LexiconError('invalid entry')
        def fail():
            raise error
        with self.assertRaises(NLPError) as caught:
            run_stage('grammar', fail)
        self.assertIs(caught.exception, error)
        self.assertIn('[lexical:LEXICON_INVALID]', str(error))

    def test_no_parse_is_expected_result_in_trace(self):
        result = CourseAssistant().process('thời tiết hôm nay thế nào?')
        self.assertEqual(result['status'], 'parse_failed')
        self.assertEqual(result['error']['stage'], 'parsing')
        self.assertEqual(result['parse_tree'], '()')
