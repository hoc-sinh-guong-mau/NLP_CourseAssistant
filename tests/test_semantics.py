import unittest
from nltk import Tree
from nltk.featstruct import TYPE, Variable
from nltk.grammar import FeatStructNonterminal
from src.parsing.parser import Parser, load_grammar
from src.preprocessing.preprocessor import normalize, tokenize
from src.semantic import SemanticInterpreter, InvalidSemanticError, UnsupportedSemanticError, SemanticRule
from src.semantic.rules import SEMANTIC_RULES
from src.application.pipeline import CourseAssistant
from src.config import ROOT


class SemanticTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.parser = Parser()
        cls.semantic = SemanticInterpreter()

    def test_grammar_qtypes_have_schemas(self):
        keys = {(p.lhs().get('INTENT'), p.lhs().get('QTYPE'))
                for p in load_grammar().productions()
                if isinstance(p.lhs().get('INTENT'), str) and isinstance(p.lhs().get('QTYPE'), str)}
        self.assertFalse(keys - SEMANTIC_RULES.keys())

    def test_roles_and_composition(self):
        cases = [
            ('Môn NLP thuộc khoa nào?', {'course_id': 'CO3085'}),
            ('Giữa kỳ bao nhiêu phút?', {'exam_id': 'MIDTERM'}),
            ('Tuần ba học gì?', {'week_id': 'WEEK_03'}),
            ('Chương 3 có CFG không?', {'chapter_id': 'CH03', 'topic_id': 'CFG'}),
            ('CFG và parsing nằm ở tuần nào?', {'topic_ids': ['CFG', 'PARSING']}),
            ('Phần i của btl yêu cầu gì?', {'part_id': 'PART_I', 'assignment_id': 'BTL01'}),
            ('Btl có parser không?', {'component_id': 'PART_I', 'assignment_id': 'BTL01'}),
            ('Có được dùng AI không?', {'rule_id': 'AI_USAGE'}),
            ('Btl có được dùng AI không?', {'rule_id': 'AI_USAGE', 'assignment_id': 'BTL01'}),
            ('L.O.2.5 là gì?', {'learning_outcome_id': 'LO2.5'}),
            ('Còn chương sau?', {'context_ref': 'CONTEXT_REF'}),
        ]
        for text, expected in cases:
            with self.subTest(text=text):
                trees = self.parser.parse_all(tokenize(normalize(text)))
                self.assertTrue(trees)
                for tree in trees:
                    self.assertEqual(self.semantic.interpret(tree).arguments, expected)

    def test_existing_input_has_no_semantic_failures(self):
        for text in (ROOT / 'input/sentences.txt').read_text().splitlines():
            for tree in self.parser.parse_all(tokenize(normalize(text))):
                with self.subTest(text=text):
                    self.semantic.interpret(tree)

    def test_unknown_and_unresolved_features(self):
        for features, error in [
            ({'INTENT':'UNKNOWN','QTYPE':'UNKNOWN'}, UnsupportedSemanticError),
            ({'INTENT':'GET_DEADLINE','QTYPE':'DEADLINE','ENTITY':Variable('?e')}, InvalidSemanticError),
            ({'INTENT':'GET_DEADLINE','QTYPE':'DEADLINE'}, InvalidSemanticError),
        ]:
            tree = Tree(FeatStructNonterminal({TYPE:'S', **features}), [])
            with self.assertRaises(error):
                self.semantic.interpret(tree)

    def test_custom_schemas_are_isolated(self):
        rules = {('CUSTOM','INFO'): SemanticRule({'object_id':'ENTITY'})}
        interpreter = SemanticInterpreter(rules)
        rules[('CUSTOM','INFO')].slots['wrong'] = 'TARGET'
        tree = Tree(FeatStructNonterminal({TYPE:'S','INTENT':'CUSTOM','QTYPE':'INFO','ENTITY':'NEW'}), [])
        self.assertEqual(interpreter.interpret(tree).arguments, {'object_id':'NEW'})
        with self.assertRaises(UnsupportedSemanticError):
            self.semantic.interpret(tree)

    def test_pipeline_context_is_not_treated_as_resolved(self):
        self.assertEqual(CourseAssistant().process('Còn chương sau?')['status'], 'needs_context')
