import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock

from src.application.runner import AssignmentRunner
from src.config import ROOT, SQLITE_PATH, RunConfig
from src.evaluation.evaluator import evaluate
from src.evaluation.exceptions import EvaluationError
from src.parsing import GenerationError


class WorkflowTests(unittest.TestCase):
    def test_run_with_isolated_config_creates_aligned_outputs(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            sentences = root/'questions.txt'
            sentences.write_text('Môn NLP có mấy tín chỉ?\n\nThời tiết hôm nay thế nào?\n',encoding='utf-8')
            cases = root/'cases.jsonl'
            cases.write_text(json.dumps({'input':'Deadline btl là khi nào?', 'expected':{'status':'missing_information'}}),encoding='utf-8')
            config = RunConfig(input_path=sentences, output_dir=root/'outputs',
                               database=root/'db/kb.sqlite3', evaluation_path=cases, sample_limit=3)
            runner = AssignmentRunner(config)
            report = runner.run()
            self.assertEqual((report['passed'],report['total']),(1,1))
            for filename in ('parse-results.txt','semantic.txt','intent-entity.txt','query.txt','answer.txt'):
                with self.subTest(filename=filename):
                    self.assertEqual(len((config.output_dir/filename).read_text().splitlines()),3)
            queries = [json.loads(line) for line in (config.output_dir/'query.txt').read_text().splitlines()]
            self.assertEqual(queries[0]['filters'],{'id':'CO3085'})
            self.assertEqual(queries[1:],[None,None])
            self.assertTrue((config.output_dir/'grammar.txt').is_file())
            self.assertEqual(len((config.output_dir/'samples.txt').read_text().splitlines()),3)
            self.assertEqual({p.name for p in config.output_dir.iterdir()}, {
                'grammar.txt','samples.txt','parse-results.txt','semantic.txt',
                'intent-entity.txt','query.txt','answer.txt','evaluation.txt','dialogue.txt',
            })
            original = runner.assistant
            runner.build_kb()
            self.assertIsNot(runner.assistant,original)

    def test_invalid_run_limit_does_not_build_database(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory,'kb.sqlite3')
            with self.assertRaises(GenerationError):
                AssignmentRunner(RunConfig(database=path,sample_limit=0)).run()
            self.assertFalse(path.exists())

    def test_evaluation_rejects_empty_and_malformed_cases_before_processing(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            for text in ('', '{}\n', '{"input":"x","expected":{}}\n'):
                path=root/'cases.jsonl'
                path.write_text(text,encoding='utf-8')
                assistant=Mock()
                with self.subTest(text=text), self.assertRaises(EvaluationError):
                    evaluate(assistant,cases_path=path,output_path=root/'evaluation.txt')
                assistant.process.assert_not_called()

    def test_cli_rejects_invalid_limits(self):
        result=subprocess.run([sys.executable,'-m','src.main','run','--limit','10001'],
                              cwd=ROOT,capture_output=True,text=True,
                                  env={**os.environ, 'COURSE_DATABASE': str(SQLITE_PATH)})
        self.assertEqual(result.returncode,2)
        self.assertIn('limit must be between',result.stderr)

    def test_cli_each_stage_exports_only_its_required_files(self):
        outputs = {
            'grammar': {'grammar.txt'},
            'generate': {'samples.txt'},
            'parse': {'parse-results.txt'},
            'semantic': {'semantic.txt'},
            'intent-entity': {'intent-entity.txt'},
            'query': {'query.txt'},
            'answer': {'answer.txt'},
            'batch': {'semantic.txt','intent-entity.txt','query.txt','answer.txt'},
            'evaluate': {'evaluation.txt'},
        }
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            source=root/'input.txt'
            source.write_text('Môn NLP có mấy tín chỉ?\n\nThời tiết hôm nay?\n',encoding='utf-8')
            for command,expected in outputs.items():
                with self.subTest(command=command):
                    output=root/command
                    args=[sys.executable,'-m','src.main',command,'--output-dir',str(output)]
                    if command == 'generate':args+=['--limit','3']
                    if command in {'parse','semantic','intent-entity','query','answer','batch'}:
                        args+=['--input',str(source)]
                    result=subprocess.run(args,cwd=ROOT,capture_output=True,text=True,
                                  env={**os.environ, 'COURSE_DATABASE': str(SQLITE_PATH)})
                    self.assertEqual(result.returncode,0,result.stderr)
                    self.assertEqual({p.name for p in output.iterdir()},expected)
                    if 'query.txt' in expected:
                        lines=(output/'query.txt').read_text().splitlines()
                        self.assertEqual(len(lines),3)
                        self.assertEqual([json.loads(line) for line in lines[1:]],[None,None])

    def test_early_pipeline_stages_do_not_execute_later_stages(self):
        from src.application.pipeline import CourseAssistant
        query=Mock()
        query.build.side_effect=RuntimeError('Query must not run yet')
        assistant=CourseAssistant(query_builder=query,kb=Mock())
        for stage in ('semantic','intent_entity'):
            with self.subTest(stage=stage):
                result=assistant.process('Môn NLP có mấy tín chỉ?',stop_after=stage)
                self.assertEqual(result['status'],stage+'_ready')
                self.assertIsNone(result['query'])
        query.build.assert_not_called()
        kb=Mock()
        kb.execute.side_effect=RuntimeError('Retrieval must not run yet')
        answer=Mock()
        assistant=CourseAssistant(kb=kb,answer_generator=answer)
        result=assistant.process('Môn NLP có mấy tín chỉ?',stop_after='query')
        self.assertEqual(result['status'],'query_ready')
        self.assertEqual(result['query']['select'],['credits'])
        kb.execute.assert_not_called()
        answer.render.assert_not_called()


    def test_numbered_part_commands_are_rejected(self):
        for name in ('part1','part2','part3','part4'):
            with self.subTest(command=name):
                result=subprocess.run([sys.executable,'-m','src.main',name],cwd=ROOT,capture_output=True,text=True,
                                  env={**os.environ, 'COURSE_DATABASE': str(SQLITE_PATH)})
                self.assertEqual(result.returncode,2)
                self.assertIn('invalid choice',result.stderr)
