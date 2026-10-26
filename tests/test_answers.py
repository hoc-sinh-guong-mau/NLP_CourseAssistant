import json
from pathlib import Path
import tempfile
import unittest

from src.application.pipeline import CourseAssistant
from src.artifacts.exporter import export_records
from src.generation import AnswerGenerator
from src.generation.answer import ANSWER_HANDLERS
from src.retrieval import QueryBuilder
from src.retrieval.query_rules import QUERY_SPECS
from src.retrieval.sqlite import SQLiteKnowledgeBase
from src.semantic import SemanticFrame


class AnswerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=CourseAssistant()
        cls.renderer=AnswerGenerator()

    def test_answer_registry_covers_all_business_queries(self):
        self.assertEqual(set(ANSWER_HANDLERS),set(QUERY_SPECS))
        args={'course_id':'CO3085','week_id':'WEEK_03','chapter_id':'CH03',
              'topic_id':'CFG','topic_ids':['CFG','PCFG'],'course_part_id':'SYNTACTIC_PROCESSING',
              'assignment_id':'BTL01','part_id':'PART_I','component_id':'PART_I',
              'resource_id':'REFERENCE_2','resource_category_id':'PYTHON_NLP',
              'learning_outcome_id':'LO2.5','rule_id':'AI_USAGE','exam_id':'MIDTERM',
              'assessment_item_id':'MIDTERM'}
        builder=QueryBuilder()
        kb=SQLiteKnowledgeBase()
        for intent,qtype in QUERY_SPECS:
            with self.subTest(intent=intent,qtype=qtype):
                frame=SemanticFrame(intent,args,qtype)
                status,text=self.renderer.render(frame,kb.execute(builder.build(frame)))
                self.assertIn(status,('ok','missing_information'))
                self.assertTrue(text.strip())
                self.assertNotIn('None',text)
                self.assertNotIn('[]',text)

    def test_end_to_end_grounded_answers(self):
        cases=[
            ('Môn NLP có mấy tín chỉ?', ['3 tín chỉ','course_info.txt']),
            ('Tuần ba học gì?', ['Tuần 3','context-free grammar','dữ liệu mẫu']),
            ('Chương nào nói về PCFG?', ['Chương 3','Chương 6','topics.txt']),
            ('Bài tập lớn nhóm mấy người?', ['3–4 sinh viên','dữ liệu mẫu']),
            ('Phần i của btl cần xuất file gì?', ['grammar.txt','samples.txt','parse-results.txt']),
            ('Tài liệu nào liên quan đến Python NLP?', ['Natural Language Processing with Python','Steven Bird']),
            ('Midterm bao nhiêu phút?', ['60 phút']),
            ('L.O.2.5 là gì?', ['LO2.5','xác suất']),
        ]
        for text, expected in cases:
            with self.subTest(text=text):
                record=self.app.process(text)
                self.assertEqual(record['status'],'ok')
                for fragment in expected:self.assertIn(fragment,record['answer'])

    def test_absent_data_is_not_fabricated(self):
        for text in ('Deadline btl là khi nào?','Giảng viên môn NLP là ai?',
                     'Tài liệu nào nói về CFG?', 'reference'):  # last item is a parse failure
            with self.subTest(text=text):
                record=self.app.process(text)
                self.assertIn(record['status'],('missing_information','parse_failed'))
                self.assertNotIn('2030',record['answer'])
        frame=SemanticFrame('GET_RESOURCE',{'resource_id':'REFERENCE_5'},'RESOURCE_YEAR')
        records=SQLiteKnowledgeBase().execute(QueryBuilder().build(frame))
        self.assertEqual(self.renderer.render(frame,records)[0],'missing_information')

    def test_partial_relations_do_not_produce_false_negative(self):
        frame=SemanticFrame('GET_TOPIC',{'chapter_id':'CH03','topic_id':'ELLIPSIS'},'CHAPTER_HAS_TOPIC')
        row={'id':'CH03','number':3,'title':'Grammar and Parsing','topic_ids':['CFG'],
             'topic_links_complete':False}
        status,text=self.renderer.render(frame,[row])
        self.assertEqual(status,'missing_information')
        self.assertIn('chưa thể kết luận',text)
        row['topic_links_complete']=True
        status,text=self.renderer.render(frame,[row])
        self.assertEqual(status,'ok')
        self.assertTrue(text.startswith('Không.'))
        row['topic_ids'].append('ELLIPSIS')
        self.assertTrue(self.renderer.render(frame,[row])[1].startswith('Có.'))

    def test_unknown_policy_permission_is_not_a_yes(self):
        record=self.app.process('Có được dùng AI không?')
        self.assertEqual(record['status'],'missing_information')
        self.assertIn('khai báo',record['answer'])
        self.assertIn('regulations.txt',record['answer'])
        self.assertIn('dữ liệu mẫu',record['answer'])
        frame=SemanticFrame('GET_RULE',{'rule_id':'AI_USAGE'},'PERMISSION')
        row={'id':'AI_USAGE','description':'Example policy','permission':False}
        self.assertTrue(self.renderer.render(frame,[row])[1].startswith('Không.'))
        frame.arguments['assignment_id']='BTL01'
        self.assertEqual(self.renderer.render(frame,[row])[0],'missing_information')

    def test_false_and_zero_are_known_values(self):
        frame=SemanticFrame('GET_COURSE_INFO',{'exam_id':'MIDTERM'},'EXAM_OPEN_BOOK')
        status,text=self.renderer.render(frame,[{'open_book':False}])
        self.assertEqual(status,'ok')
        self.assertIn('không được',text)
        frame=SemanticFrame('GET_COURSE_INFO',{'assessment_item_id':'MIDTERM'},'ASSESSMENT_WEIGHT')
        self.assertIn('0%',self.renderer.render(frame,[{'weight_percent':0}])[1])

    def test_empty_results_are_handled_for_every_template(self):
        for intent,qtype in ANSWER_HANDLERS:
            with self.subTest(intent=intent,qtype=qtype):
                status,text=self.renderer.render(SemanticFrame(intent,{},qtype),[])
                self.assertEqual(status,'missing_information')
                self.assertTrue(text)

    def test_output_contains_answers_and_preserves_order(self):
        records=[self.app.process(text) for text in ('Môn NLP có mấy tín chỉ?', 'Deadline btl là khi nào?', 'Thời tiết hôm nay?')]
        with tempfile.TemporaryDirectory() as directory:
            export_records(records,directory)
            lines=(Path(directory)/'answer.txt').read_text(encoding='utf-8').splitlines()
            self.assertEqual(lines,[r['answer'] for r in records])
            self.assertIn('3 tín chỉ',lines[0])
            self.assertEqual([r['status'] for r in records],['ok','missing_information','parse_failed'])
            self.assertEqual({p.name for p in Path(directory).iterdir()},
                             {'semantic.txt','intent-entity.txt','query.txt','answer.txt'})
