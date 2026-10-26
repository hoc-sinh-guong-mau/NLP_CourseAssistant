import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from src.application.pipeline import CourseAssistant
from src.config import ROOT
from src.dialogue import DialogueSession
from src.retrieval import KnowledgeBase


class DialogueTests(unittest.TestCase):
    def setUp(self):
        self.session=DialogueSession(CourseAssistant())

    def test_assignment_part_reference_uses_existing_pipeline(self):
        first=self.session.process('Bài tập lớn có phần parser không?')
        second=self.session.process('Phần này cần xuất file gì?')
        self.assertEqual(first['status'],'ok')
        self.assertEqual(second['raw_semantic']['predicate'],'CONTEXT_DEPENDENT')
        self.assertEqual(second['semantic']['arguments'],{'part_id':'PART_I','assignment_id':'BTL01'})
        self.assertEqual(second['query']['filters'],{'id':'PART_I','assignment_id':'BTL01'})
        self.assertEqual(second['context_used']['source_turn'],1)
        self.assertIn('output/grammar.txt',second['answer'])
        self.assertEqual(second['status'],'ok')

    def test_chapter_pronoun_and_next_chapter(self):
        self.session.process('Chương 4 nói về gì?')
        related=self.session.process('Nó có liên quan đến parsing không?')
        self.assertEqual(related['semantic']['arguments'],{'chapter_id':'CH04','topic_id':'PARSING'})
        self.assertTrue(related['answer'].startswith('Có.'))
        self.session.process('Chương 11 có hỏi đáp không?')
        following=self.session.process('Còn chương sau?')
        self.assertEqual(following['semantic']['arguments'],{'chapter_id':'CH12'})
        state=following['context_after']
        failure=self.session.process('Còn chương sau?')
        self.assertEqual(failure['status'],'needs_context')
        self.assertEqual(failure['context_after'],state)

    def test_course_reference_switches_from_assignment_to_parent_course(self):
        self.session.process('Bài tập lớn yêu cầu gì?')
        result=self.session.process('Môn này có bao nhiêu chương?')
        self.assertEqual(result['semantic']['arguments'],{'course_id':'CO3085'})
        self.assertEqual(result['semantic']['qtype'],'CHAPTER_COUNT')
        self.assertIn('12 chương',result['answer'])
        self.assertEqual(result['context_after']['focus'],'course')
        # Do not use an unrelated stale chapter after changing the topic.
        self.assertEqual(self.session.process('Nó có liên quan đến parsing không?')['status'],'needs_context')

    def test_missing_context_reset_and_separate_sessions(self):
        self.assertEqual(self.session.process('Phần này cần xuất file gì?')['status'],'needs_context')
        self.session.process('Bài tập lớn có phần parser không?')
        independent=DialogueSession(self.session.assistant)
        self.assertEqual(independent.process('Phần này cần xuất file gì?')['status'],'needs_context')
        self.session.reset()
        result=self.session.process('Phần này cần xuất file gì?')
        self.assertEqual(result['turn'],1)
        self.assertEqual(result['status'],'needs_context')

    def test_week_context_derives_chapter_without_inventing_resources(self):
        self.session.process('Tuần 5 học những gì?')
        result=self.session.process('Tài liệu của phần này ở đâu?')
        self.assertEqual(result['semantic']['arguments'],{'chapter_id':'CH04'})
        self.assertEqual(result['semantic']['qtype'],'RESOURCE_BY_CHAPTER')
        self.assertEqual(result['status'],'missing_information')
        self.assertEqual(result['result'],[])

    def test_learning_outcome_reference_keeps_missing_link_unknown(self):
        self.session.process('L.O.2.5 học về gì?')
        result=self.session.process('Nội dung này nằm ở chương nào?')
        self.assertEqual(result['semantic']['arguments'],{'learning_outcome_id':'LO2.5'})
        self.assertEqual(result['status'],'missing_information')
        self.assertNotIn('Chương 6',result['answer'])

    def test_multiple_chapters_require_clarification(self):
        kb=KnowledgeBase()
        kb.collections['schedule'][2]['chapter_ids']=['CH03','CH04']
        session=DialogueSession(CourseAssistant(kb=kb))
        session.process('Tuần 3 học gì?')
        result=session.process('Nó có liên quan đến parsing không?')
        self.assertEqual(result['status'],'needs_context')
        self.assertEqual(result['error']['context']['candidates'],['CH03','CH04'])
        self.assertIsNone(result['query'])

    def test_failed_turn_and_external_record_mutation_do_not_corrupt_context(self):
        first=self.session.process('Chương 4 nói về gì?')
        first['context_after']['entities']['chapter'].append('CH99')
        failed=self.session.process('Thời tiết hôm nay thế nào?')
        self.assertEqual(failed['status'],'parse_failed')
        self.assertEqual(failed['context_after']['entities']['chapter'],['CH04'])
        result=self.session.process('Nó có liên quan đến parsing không?')
        self.assertEqual(result['context_used']['source_turn'],1)
        self.assertEqual(result['semantic']['arguments']['chapter_id'],'CH04')

    def test_dialogue_cli_outputs_only_dialogue_and_resets_between_groups(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            source=root/'dialogues.txt'
            source.write_text('Bài tập lớn có phần parser không?\nPhần này cần xuất file gì?\n\nPhần này cần xuất file gì?\n',encoding='utf-8')
            result=subprocess.run([sys.executable,'-m','src.main','dialogue','--input',str(source),'--output-dir',str(root/'out')],
                                  cwd=ROOT,capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertEqual({p.name for p in (root/'out').iterdir()},{'dialogue.txt'})
            text=(root/'out/dialogue.txt').read_text()
            for label in ('INPUT:','CONTEXT_USED:','RAW_SEMANTIC:','RESOLVED_SEMANTIC:','QUERY:','ANSWER:','STATUS:'):
                self.assertIn(label,text)
            first,second=text.split('DIALOGUE 02')
            self.assertIn('output/grammar.txt',first)
            self.assertIn('STATUS: needs_context',second)
