"""Evaluation verifies outputs and failure accounting without fitting an oracle."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

from src.application.pipeline import CourseAssistant
from src.config import ROOT, SQLITE_PATH
from src.evaluation.dataset import load_cases
from src.evaluation.evaluator import evaluate
from src.evaluation.exceptions import EvaluationError
from src.evaluation.metrics import summarize
from src.evaluation.scoring import score_turn


def record(intent='GET_COURSE_INFO', qtype='CREDITS', entities=None, **extra):
    return {'intent_entity': {'intent': intent, 'qtype': qtype,
                             'entities': {'course_id': 'CO3085'} if entities is None else entities},
            'parse_tree': '(S)', 'status': 'ok', 'answer': 'Môn CO3085 có 3 tín chỉ.',
            'result': [{'credits': 3}], **extra}


def scored(expected, actual):
    return {'elapsed_ms': 1.0, **score_turn(expected, actual)}


def summary(rows):
    return summarize([{'id': 'example', 'tags': ['test'], 'dialogue': False,
                       'correct': all(row['correct'] for row in rows), 'turns': rows}])


class EvaluationDatasetTests(unittest.TestCase):
    def load(self, rows):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'cases.jsonl'
            path.write_text(''.join(json.dumps(row) + '\n' for row in rows))
            return load_cases(path)

    def test_accepts_legacy_and_dialogue_cases(self):
        cases = self.load([{'input': 'Question?', 'expected': {'status': 'ok'}},
                           {'id': 'dialogue', 'tags': ['reference'], 'turns': [
                               {'input': 'Follow up?', 'expected': {'status': 'needs_context'}}]}])
        self.assertEqual(cases[0]['id'], 'case_001')
        self.assertFalse(cases[0]['dialogue'])
        self.assertTrue(cases[1]['dialogue'])

    def test_rejects_invalid_labels_and_ambiguous_formats(self):
        invalid = [
            {'input': '', 'expected': {'status': 'ok'}},
            {'input': 'q', 'expected': {}},
            {'input': 'q', 'expected': {'intnet': 'GET_TOPIC'}},
            {'input': 'q', 'expected': {'entities': {'week_id': []}}},
            {'input': 'q', 'expected': {'entities': {'week_id': {'id': 'WEEK_03'}}}},
            {'input': 'q', 'expected': {'result_contains': []}},
            {'input': 'q', 'expected': {'answer_contains': []}},
            {'input': 'q', 'expected': {'query': 'SELECT *'}},
            {'input': 'q', 'expected': {'semantic': {'wrong': 'keys'}}},
            {'input': 'q', 'expected': {'intent': 'GET_TOPIC', 'intent_entity': {
                'intent': 'GET_COURSE_INFO', 'qtype': 'CREDITS', 'entities': {'course_id': 'CO3085'}}}},
            {'input': 'q', 'expected': {'status': 'ok'}, 'turns': []},
            {'turns': [{'input': 'q', 'expected': {'status': 'ok'}, 'typo': True}]},
        ]
        for row in invalid:
            with self.subTest(row=row), self.assertRaises(EvaluationError):
                self.load([row])
        with self.assertRaises(EvaluationError):
            self.load([{'id': 'same', 'input': 'q', 'expected': {'status': 'ok'}}] * 2)

    def test_malformed_json_is_an_evaluation_error_with_line_number(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'cases.jsonl'
            path.write_text('\n{bad json}\n')
            with self.assertRaises(EvaluationError) as error:
                load_cases(path)
            self.assertEqual(error.exception.context['line'], 2)
            path.write_text('{"input":"q","expected":{"result_contains":[{"credits":NaN}]}}\n')
            with self.assertRaises(EvaluationError):
                load_cases(path)

    def test_invalid_dataset_does_not_initialize_or_process_models(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'cases.jsonl'
            path.write_text('{}\n')
            with patch('src.evaluation.evaluator.CourseAssistant') as assistant:
                with self.assertRaises(EvaluationError):
                    evaluate(cases_path=path, output_path=Path(directory) / 'out.txt')
                assistant.assert_not_called()


class EvaluationMetricTests(unittest.TestCase):
    def test_classification_counts_abstentions_and_reports_macro_f1(self):
        rows = [scored({'intent': 'GET_COURSE_INFO'}, record()),
                scored({'intent': 'GET_TOPIC'}, record()),
                scored({'intent': 'GET_TOPIC'}, record(intent='GET_TOPIC')),
                scored({'intent': 'UNKNOWN'}, record(intent_entity=None, parse_tree='()'))]
        metrics = summary(rows)['intent']
        self.assertEqual(metrics['total'], 4)
        self.assertEqual(metrics['accuracy'], 0.75)
        self.assertAlmostEqual(metrics['macro_f1'], (2/3 + 2/3 + 1)/3)
        self.assertIn({'expected': 'GET_TOPIC', 'predicted': 'GET_COURSE_INFO', 'count': 1}, metrics['confusion'])

    def test_entities_use_slot_and_id_sets_and_penalize_hallucinated_entities(self):
        rows = [scored({'entities': {'topic_ids': ['CFG', 'PARSING']}},
                       record(entities={'topic_ids': ['PARSING', 'CFG']})),
                scored({'entities': {'week_id': 'WEEK_03'}}, record(entities={'week_id': 'WEEK_04'})),
                scored({'entities': {}}, record())]
        metrics = summary(rows)['entities']
        self.assertEqual(metrics['true_positive'], 2)
        self.assertEqual(metrics['false_positive'], 2)
        self.assertEqual(metrics['false_negative'], 1)
        self.assertEqual(metrics['micro_precision'], 0.5)
        self.assertAlmostEqual(metrics['micro_recall'], 2/3)
        self.assertAlmostEqual(metrics['micro_f1'], 4/7)
        self.assertAlmostEqual(metrics['exact_match']['accuracy'], 1/3)

    def test_unlabeled_components_are_not_silently_scored(self):
        metrics = summary([scored({'status': 'ok'}, record())])
        self.assertEqual(metrics['status']['accuracy'], 1)
        for key in ('intent', 'qtype', 'query_exact_match', 'answer'):
            self.assertEqual(metrics[key]['total'], 0)
            self.assertIsNone(metrics[key]['accuracy'])
        self.assertIsNone(metrics['entities']['micro_f1'])

    def test_query_order_is_ignored_but_wrong_filters_are_errors(self):
        expected = {'collection': 'course', 'filters': {'id': 'CO3085'}, 'select': ['credits', 'id']}
        self.assertTrue(score_turn({'query': expected}, record(query={**expected, 'select': ['id', 'credits']}))['correct'])
        self.assertFalse(score_turn({'query': expected}, record(query={**expected, 'filters': {'id': 'WRONG'}}))['correct'])

    def test_facts_answer_and_context_have_separate_checks(self):
        result = scored({'result_contains': [{'credits': 3}], 'answer_contains': ['3 tín chỉ'],
                         'answer_not_contains': ['4 tín chỉ'], 'context_used': {'source_turn': 1}},
                        record(context_used={'source_turn': 1, 'entities': {'course': ['CO3085']}}))
        self.assertTrue(result['correct'])
        incorrect_answer = scored({'result_contains': [{'credits': 3}], 'answer_contains': ['3 tín chỉ']},
                                  record(answer='Có 4 tín chỉ.'))
        metrics = summary([incorrect_answer])
        self.assertEqual(metrics['retrieved_facts']['accuracy'], 1)
        self.assertEqual(metrics['answer']['accuracy'], 0)
        self.assertFalse(score_turn({'context_used': {}}, record(context_used={'source_turn': 1}))['correct'])

    def test_semantic_frame_metrics_do_not_substitute_intent_accuracy(self):
        labels = {'intent': 'GET_COURSE_INFO', 'qtype': 'CREDITS', 'entities': {'course_id': 'CO3085'}}
        row = scored(labels, record(semantic={'predicate': 'GET_COURSE_INFO', 'qtype': 'CREDITS',
                                             'arguments': {'course_id': 'WRONG'}}))
        metrics = summary([row])
        self.assertEqual(metrics['intent']['accuracy'], 1)
        self.assertEqual(metrics['semantic_frame_accuracy']['accuracy'], 0)

    def test_unknown_false_acceptance_and_fallback_attempts(self):
        rows = [scored({'intent': 'UNKNOWN'}, record(statistical_used=True, statistical_attempted=True)),
                scored({'intent': 'UNKNOWN'}, record(intent_entity=None, parse_tree='()',
                       statistical_prediction={'qtype': 'UNKNOWN', 'confidence': 0.01}))]
        metrics = summary(rows)
        self.assertEqual(metrics['unknown_requests']['false_acceptance_rate'], 0.5)
        self.assertEqual(metrics['fallback']['attempted'], 2)
        self.assertEqual(metrics['fallback']['accepted'], 1)
        self.assertEqual(metrics['fallback']['acceptance_rate'], 0.5)
        self.assertEqual(metrics['fallback']['accepted_semantic_accuracy']['total'], 0)


class EvaluationRunnerTests(unittest.TestCase):
    def test_comparison_reports_recoveries_regressions_and_one_output(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / 'cases.jsonl'
            path.write_text(''.join(json.dumps({'id': str(i), 'input': f'question {i}',
                             'tags': ['paraphrase'], 'expected': {'status': 'ok'}}) + '\n' for i in range(3)))
            hybrid = Mock(statistical_recognizer=None)
            baseline = Mock(statistical_recognizer=None)
            hybrid.process.side_effect = [record(statistical_used=True), record(status='parse_failed'), record()]
            baseline.process.side_effect = [record(status='parse_failed'), record(), record()]
            report = evaluate(hybrid, cases_path=path, output_path=root/'out/evaluation.txt',
                              compare=True, baseline=baseline)
            self.assertEqual((report['passed'], report['total']), (2, 3))
            self.assertEqual(report['comparison']['recovered_turns'], 1)
            self.assertEqual(report['comparison']['regressed_turns'], 1)
            self.assertEqual(report['metrics']['groups']['paraphrase']['cases']['total'], 3)
            self.assertEqual(len(report['failures']), 2)
            self.assertEqual({file.name for file in (root/'out').iterdir()}, {'evaluation.txt'})
            saved = json.loads((root/'out/evaluation.txt').read_text())
            self.assertEqual(saved['dataset']['sha256'], report['dataset']['sha256'])
            self.assertEqual(saved['systems']['grammar_only']['metrics']['case_accuracy']['correct'], 2)

    def test_input_cannot_be_overwritten_and_system_errors_propagate(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'cases.jsonl'
            path.write_text('{"input":"q","expected":{"status":"ok"}}\n')
            with self.assertRaises(EvaluationError):
                evaluate(cases_path=path, output_path=path)
            assistant = Mock()
            assistant.process.side_effect = RuntimeError('unexpected system failure')
            with self.assertRaisesRegex(RuntimeError, 'system failure'):
                evaluate(assistant, cases_path=path, output_path=Path(directory)/'out.txt')
            self.assertFalse((Path(directory)/'out.txt').exists())

    def test_explicit_grammar_only_never_loads_model(self):
        with patch('src.application.pipeline._load_statistical_recognizer') as loader:
            assistant = CourseAssistant(use_statistical=False)
        loader.assert_not_called()
        answer = assistant.process('Bạn cho mình hỏi số tín chỉ của NLP với')
        self.assertFalse(answer['statistical_attempted'])
        self.assertEqual(answer['status'], 'parse_failed')

    def test_comparison_and_dialogue_cases_are_isolated(self):
        cases = [
            {'id': 'with_context', 'turns': [
                {'input': 'Bài tập lớn có phần parser không?', 'expected': {'status': 'ok'}},
                {'input': 'Phần này cần xuất file gì?', 'expected': {'status': 'ok', 'context_used': {'source_turn': 1}}}]},
            {'id': 'without_context', 'turns': [
                {'input': 'Phần này cần xuất file gì?', 'expected': {'status': 'needs_context'}}]},
        ]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'cases.jsonl'
            path.write_text(''.join(json.dumps(case) + '\n' for case in cases))
            report = evaluate(CourseAssistant(use_statistical=False), cases_path=path,
                              output_path=Path(directory)/'evaluation.txt', compare=True)
            self.assertEqual((report['passed'], report['total']), (2, 2))
            for system in report['systems'].values():
                self.assertEqual(system['metrics']['dialogue']['session_accuracy']['accuracy'], 1)
                self.assertEqual(system['cases'][1]['turns'][0]['actual']['context_before']['entities'], {})

    def test_cli_reads_custom_cases_and_compares_systems(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root/'cases.jsonl'
            path.write_text('{"input":"Môn NLP có mấy tín chỉ?","expected":{"status":"ok"}}\n')
            result = subprocess.run([sys.executable, '-m', 'src.main', 'evaluate', '--compare',
                                     '--input', str(path), '--output-dir', str(root/'out')],
                                    cwd=ROOT, env={**os.environ, 'COURSE_DATABASE': str(SQLITE_PATH)},
                                    capture_output=True, text=True, timeout=60)
            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads((root/'out/evaluation.txt').read_text())
            self.assertEqual(report['dataset']['cases'], 1)
            self.assertEqual(set(report['systems']), {'grammar_only', 'hybrid'})
            path.write_text('{"input":"Môn NLP có mấy tín chỉ?","expected":{"status":"needs_context"}}\n')
            result = subprocess.run([sys.executable, '-m', 'src.main', 'evaluate', '--input', str(path),
                                     '--output-dir', str(root/'failed')],
                                    cwd=ROOT, env={**os.environ, 'COURSE_DATABASE': str(SQLITE_PATH)},
                                    capture_output=True, text=True, timeout=60)
            self.assertEqual(result.returncode, 1, result.stderr)
            self.assertEqual(json.loads((root/'failed/evaluation.txt').read_text())['passed'], 0)
