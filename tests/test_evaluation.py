"""Regressions for abstention labels, null slots and startup smoke evaluation."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

from src.application.pipeline import CourseAssistant
from src.config import ROOT, SQLITE_PATH, RunConfig
from src.evaluation.evaluator import evaluate, _expected_abstention
from src.evaluation.exceptions import EvaluationError
from src.semantic import SemanticInterpreter
from src.parsing import Parser
from src.preprocessing import normalize, tokenize
from src.dialogue import DialogueSession


class EvaluationRegressionTests(unittest.TestCase):
    def run_cases(self, cases, records):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'cases.jsonl'
            output = Path(directory)/'evaluation.txt'
            path.write_text(''.join(json.dumps(case)+'\n' for case in cases), encoding='utf-8')
            assistant = Mock()
            assistant.process.side_effect = records
            report = evaluate(assistant, cases_path=path, output_path=output)
            self.assertEqual(json.loads(output.read_text(encoding='utf-8')), report)
            return report

    def test_abstain_only_labels_are_scored_for_both_decisions(self):
        for expected, actual, correct in [
            (True, {'status':'ok'}, False),
            (True, {'status':'needs_context'}, True),
            (False, {'status':'ok'}, True),
            (False, {'status':'ambiguous'}, False),
            (True, {'status':'ok','abstained':True}, True),
        ]:
            with self.subTest(expected=expected, actual=actual):
                report = self.run_cases([{'input':'q','expected':{'abstain':expected}}], [actual])
                self.assertEqual(report['passed'], int(correct))
                self.assertEqual(report['cases'][0]['checks']['abstain'], correct)
                self.assertEqual(report['cases'][0]['expected']['abstain'], expected)

    def test_abstain_and_output_checks_must_both_match(self):
        report = self.run_cases(
            [{'input':'q','expected':{'abstain':True,'answer':'clarify'}}],
            [{'status':'needs_context','answer':'wrong clarification'}])
        self.assertEqual(report['passed'], 0)
        self.assertTrue(report['cases'][0]['checks']['abstain'])
        self.assertFalse(report['cases'][0]['checks']['answer'])

    def test_every_abstention_status_is_symmetric_in_truth_and_prediction(self):
        statuses = ('missing_information','unsupported_query','unsupported_semantic','unsupported_answer',
                    'parse_failed','invalid_semantic','needs_context','ambiguous')
        cases = [{'input':status,'expected':{'status':status}} for status in statuses]
        report = self.run_cases(cases, [{'status':case['input']} for case in cases])
        self.assertEqual(report['passed'], len(cases))
        metrics = report['abstention_performance']
        self.assertEqual(metrics['abstention_accuracy'], 1)
        self.assertEqual(metrics['coverage'], 0)
        self.assertEqual(metrics['outcomes']['N5_correct_abstention'], len(cases))

    def test_unrecognized_status_does_not_become_should_answer(self):
        self.assertIsNone(_expected_abstention({'status':'custom_status'}))
        self.assertFalse(_expected_abstention({'status':'ok'}))
        self.assertIsNone(_expected_abstention({'answer':'some answer'}))
        report = self.run_cases([{'input':'q','expected':{'status':'custom_status'}}],
                                [{'status':'custom_status'}])
        self.assertIsNone(report['abstention_performance'])
        self.assertIsNotNone(report['abstention_note'])

    def test_explicit_should_answer_label_overrides_status_inference(self):
        # An answerable request may currently fail parsing; do not reward that failure.
        report = self.run_cases([{'input':'q','expected':{'status':'parse_failed','abstain':False}}],
                                [{'status':'parse_failed'}])
        self.assertEqual(report['passed'], 0)
        self.assertEqual(report['abstention_performance']['outcomes']['N3_unneeded_abstention'], 1)

    def test_null_entities_are_scored_without_crashing(self):
        for key in ('semantic','intent_entity'):
            with self.subTest(key=key):
                report = self.run_cases([{'input':'q','expected':{'status':'parse_failed',key:None}}],
                                       [{'status':'parse_failed','semantic':None,'intent_entity':None}])
                self.assertEqual(report['passed'], 1)
                self.assertEqual(report['task_performance']['entity_extraction_count'], 1)
                self.assertEqual(report['task_performance']['entity_extraction_exact_match_accuracy'], 1)
        report = self.run_cases([{'input':'q','expected':{'intent_entity':None,'abstain':True}}],
                               [{'status':'ok','intent_entity':{'intent':'GET_COURSE_INFO','entities':{'course_id':'CO3085'}}}])
        self.assertEqual(report['passed'], 0)
        self.assertEqual(report['task_performance']['entity_extraction_exact_match_accuracy'], 0)

    def test_invalid_nested_labels_and_mixed_annotations_fail_before_models_run(self):
        invalid = [
            [{'input':'q','expected':{'semantic':'not a mapping'}}],
            [{'input':'q','expected':{'intent_entity':{'entities':None}}}],
            [{'input':'q','expected':{'abstain':'yes'}}],
            [{'input':'a','expected':{'status':'ok'}},
             {'input':'b','expected':{'status':'custom_status'}}],
        ]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'cases.jsonl'
            for cases in invalid:
                path.write_text(''.join(json.dumps(case)+'\n' for case in cases), encoding='utf-8')
                with self.subTest(cases=cases), patch('src.evaluation.evaluator.CourseAssistant') as assistant:
                    with self.assertRaises(EvaluationError):
                        evaluate(cases_path=path, output_path=Path(directory)/'out.txt')
                    assistant.assert_not_called()

    def test_dataset_cannot_be_overwritten_by_report(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'cases.jsonl'
            path.write_text('original', encoding='utf-8')
            with self.assertRaises(EvaluationError):
                evaluate(cases_path=path, output_path=path)
            self.assertEqual(path.read_text(encoding='utf-8'), 'original')

    def test_startup_smoke_passes_without_requiring_benchmark_to_be_perfect(self):
        self.assertEqual(RunConfig().evaluation_path.name, 'smoke_cases.jsonl')
        self.assertTrue((ROOT/'input/test_cases.jsonl').is_file())
        self.assertNotEqual(RunConfig().evaluation_path, ROOT/'input/test_cases.jsonl')
        with tempfile.TemporaryDirectory() as directory:
            report = evaluate(cases_path=RunConfig().evaluation_path, output_path=Path(directory)/'evaluation.txt')
            self.assertEqual((report['passed'],report['total']), (3,3))

    def test_cli_accepts_a_dataset_and_keeps_failure_exit_code(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root/'custom.jsonl'
            path.write_text(json.dumps({'input':'Môn NLP có mấy tín chỉ?',
                                        'expected':{'abstain':True}})+'\n', encoding='utf-8')
            result = subprocess.run([sys.executable,'-m','src.main','evaluate','--input',str(path),
                                     '--output-dir',str(root/'out')], cwd=ROOT,
                                    env={**os.environ,'COURSE_DATABASE':str(SQLITE_PATH)},
                                    capture_output=True,text=True,timeout=60)
            self.assertEqual(result.returncode,1,result.stderr)
            report = json.loads((root/'out/evaluation.txt').read_text(encoding='utf-8'))
            self.assertEqual((report['passed'],report['total']), (0,1))
            self.assertEqual({file.name for file in (root/'out').iterdir()}, {'evaluation.txt'})


class ResourceGrammarRegressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.parser = Parser()
        cls.semantic = SemanticInterpreter()

    def test_explicit_topics_have_only_a_direct_resource_meaning(self):
        for text in ('CFG có tài liệu nào?', 'CFG có tài liệu nào không?',
                     'Tài liệu CFG là gì?', 'Tài liệu của CFG ở đâu?'):
            with self.subTest(text=text):
                trees = self.parser.parse_all(tokenize(normalize(text)))
                self.assertTrue(trees)
                frames = [self.semantic.interpret(tree) for tree in trees]
                self.assertEqual({frame.canonical_key() for frame in frames},
                                 {frames[0].canonical_key()})
                for frame in frames:
                    self.assertEqual(frame.predicate, 'GET_RESOURCE')
                    self.assertEqual(frame.qtype, 'RESOURCE_BY_TOPIC')
                    self.assertEqual(frame.arguments, {'topic_id':'CFG'})

    def test_explicit_topic_overrides_previous_chapter_context(self):
        assistant = CourseAssistant(parser=self.parser)
        session = DialogueSession(assistant)
        session.process('Chương 4 nói về gì?')
        record = session.process('CFG có tài liệu nào?')
        self.assertEqual(record['semantic']['arguments'], {'topic_id':'CFG'})
        self.assertEqual(record['semantic']['predicate'], 'GET_RESOURCE')
        self.assertEqual(record['context_used'], {})
        self.assertEqual(record['query']['conditions'], [{'field':'topic_ids','operator':'contains','value':'CFG'}])
        self.assertNotIn(record['status'], ('ambiguous','needs_context','parse_failed'))

    def test_real_references_still_need_context(self):
        for text in ('Tài liệu của phần này ở đâu?', 'Chương này có tài liệu nào?'):
            with self.subTest(text=text):
                trees = self.parser.parse_all(tokenize(normalize(text)))
                self.assertTrue(trees)
                for tree in trees:
                    self.assertEqual(self.semantic.interpret(tree).predicate, 'CONTEXT_DEPENDENT')
