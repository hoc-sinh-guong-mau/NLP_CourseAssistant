import json
import tempfile
import unittest
from pathlib import Path

from src.application.pipeline import CourseAssistant
from src.artifacts.exporter import export_records
from src.retrieval import KnowledgeBase, KnowledgeBaseError, QueryBuilder, QueryError, UnsupportedQueryError
from src.retrieval.query_rules import QUERY_SPECS
from src.semantic import SemanticFrame
from src.semantic.rules import SEMANTIC_RULES


class QueryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.builder = QueryBuilder()
        cls.kb = KnowledgeBase()
        cls.assistant = CourseAssistant()

    def test_business_semantic_schemas_have_query_specs(self):
        expected = {key for key in SEMANTIC_RULES if key[0] != 'CONTEXT_DEPENDENT'}
        self.assertEqual(set(QUERY_SPECS), expected)
        for spec in QUERY_SPECS.values():
            self.assertIn(spec.collection, self.kb.collections)

    def test_course_description_and_credits(self):
        for qtype, field in [('DESCRIPTION','description'),('CREDITS','credits')]:
            with self.subTest(qtype=qtype):
                frame = SemanticFrame('GET_COURSE_INFO', {'course_id':'CO3085'}, qtype)
                query = self.builder.build(frame)
                self.assertEqual(query, {'collection':'course','filters':{'id':'CO3085'},'select':[field]})
                records = self.kb.execute(query)
                self.assertIsNotNone(records[0][field])
                self.assertIn('source', records[0])
                self.assertNotIn('objectives', records[0])

    def test_relational_topic_and_week_queries(self):
        query = self.builder.build(SemanticFrame('GET_TOPIC',{'topic_id':'PCFG'},'FIND_CHAPTER_BY_TOPIC'))
        self.assertEqual(query['conditions'], [{'field':'topic_ids','operator':'contains','value':'PCFG'}])
        self.assertEqual([r['id'] for r in self.kb.execute(query)], ['CH03','CH06'])
        query = self.builder.build(SemanticFrame('GET_SCHEDULE',{'chapter_id':'CH04'},'CHAPTER_WEEK'))
        self.assertEqual([r['week'] for r in self.kb.execute(query)], [4,5])
        query = self.builder.build(SemanticFrame('GET_SCHEDULE',{'topic_ids':['CFG','PCFG']},'TOPICS_WEEK'))
        self.assertEqual(query['conditions'][0]['operator'],'contains_all')
        self.assertEqual([r['week'] for r in self.kb.execute(query)], [3])

    def test_relation_checks_preserve_parent_and_requested_topic(self):
        query = self.builder.build(SemanticFrame('GET_TOPIC',{'chapter_id':'CH03','topic_id':'ELLIPSIS'},'CHAPTER_HAS_TOPIC'))
        self.assertEqual(query['context'], {'topic_id':'ELLIPSIS'})
        rows = self.kb.execute(query)
        self.assertEqual(rows[0]['id'],'CH03')
        self.assertFalse(rows[0]['topic_links_complete'])
        self.assertNotIn('ELLIPSIS', rows[0]['topic_ids'])

    def test_assignment_scope_resources_and_rule_context(self):
        frame = SemanticFrame('GET_ASSIGNMENT',{'part_id':'PART_I','assignment_id':'BTL01'},'PART_OUTPUTS')
        query = self.builder.build(frame)
        self.assertEqual(query['filters'],{'id':'PART_I','assignment_id':'BTL01'})
        self.assertIn('output/grammar.txt',self.kb.execute(query)[0]['outputs'])
        frame = SemanticFrame('GET_RESOURCE',{'course_id':'CO3085'},'TEXTBOOK_LIST')
        query = self.builder.build(frame)
        self.assertEqual(query['filters'],{'course_id':'CO3085','kind':'textbook'})
        self.assertEqual(len(self.kb.execute(query)),3)
        frame = SemanticFrame('GET_RESOURCE',{'resource_category_id':'PYTHON_NLP'},'RESOURCE_BY_CATEGORY')
        self.assertEqual([r['id'] for r in self.kb.execute(self.builder.build(frame))],['REFERENCE_2'])
        frame = SemanticFrame('GET_RULE',{'rule_id':'AI_USAGE','assignment_id':'BTL01'},'PERMISSION')
        query = self.builder.build(frame)
        self.assertEqual(query['context'],{'assignment_id':'BTL01'})
        self.assertIsNone(self.kb.execute(query)[0]['permission'])

    def test_missing_values_are_not_fabricated(self):
        frame = SemanticFrame('GET_INSTRUCTOR',{'course_id':'CO3085'},'INSTRUCTOR')
        self.assertEqual(self.kb.execute(self.builder.build(frame)),[])
        frame = SemanticFrame('GET_RESOURCE',{'resource_id':'REFERENCE_5'},'RESOURCE_YEAR')
        self.assertIsNone(self.kb.execute(self.builder.build(frame))[0]['year'])
        frame = SemanticFrame('GET_DEADLINE',{'assignment_id':'BTL01'},'DEADLINE')
        self.assertIsNone(self.kb.execute(self.builder.build(frame))[0]['deadline'])

    def test_missing_invalid_slots_and_context_are_rejected(self):
        for args in ({},{'week_id':''},{'week_id':['WEEK_03']}):
            with self.subTest(args=args), self.assertRaises(QueryError):
                self.builder.build(SemanticFrame('GET_SCHEDULE',args,'WEEK_CONTENT'))
        for topics in ([], 'CFG', ['CFG',None]):
            with self.subTest(topics=topics), self.assertRaises(QueryError):
                self.builder.build(SemanticFrame('GET_SCHEDULE',{'topic_ids':topics},'TOPICS_WEEK'))
        with self.assertRaises(QueryError):
            self.builder.build(SemanticFrame('GET_TOPIC',{'chapter_id':'CH03'},'CHAPTER_HAS_TOPIC'))
        for intent, qtype in [('UNKNOWN','UNKNOWN'),('CONTEXT_DEPENDENT','NEXT_CHAPTER')]:
            with self.assertRaises(UnsupportedQueryError):
                self.builder.build(SemanticFrame(intent,{},qtype))

    def test_unknown_operators_and_malformed_queries_are_rejected(self):
        for query in (None, {'collection':'unknown','filters':{}},
                      {'collection':'course','filters':[]},
                      {'collection':'course','filters':{},'select':'credits'},
                      {'collection':'chapters','filters':{},'conditions':[{'field':'topic_ids','operator':'eval','value':'CFG'}]},
                      {'collection':'chapters','filters':{},'conditions':[{'field':'topic_ids','operator':'contains_all','value':[]}]}):
            with self.subTest(query=query), self.assertRaises(QueryError):
                self.kb.execute(query)

    def test_results_do_not_mutate_kb(self):
        query = {'collection':'schedule','filters':{'id':'WEEK_03'},'select':['topic_ids']}
        result = self.kb.execute(query)
        result[0]['topic_ids'].append('NOT_A_TOPIC')
        self.assertNotIn('NOT_A_TOPIC',self.kb.execute(query)[0]['topic_ids'])

    def test_contains_any_and_wrong_kb_field_type(self):
        query = {'collection':'chapters','filters':{},'conditions':[{'field':'topic_ids','operator':'contains_any','value':['CFG','PCFG']}]}
        self.assertEqual([r['id'] for r in self.kb.execute(query)],['CH03','CH05','CH06'])
        query['conditions'][0]['field']='summary'
        with self.assertRaises(KnowledgeBaseError):
            self.kb.execute(query)

    def test_query_export_keeps_nulls_and_does_not_need_answer_handler(self):
        records=[self.assistant.process(text) for text in ('Môn NLP có mấy tín chỉ?', 'Thời tiết hôm nay thế nào?', 'Còn chương sau?')]
        self.assertEqual(records[0]['status'],'ok')
        self.assertIn("3 tín chỉ", records[0]["answer"])
        with tempfile.TemporaryDirectory() as directory:
            export_records(records,output_dir=directory)
            lines=(Path(directory)/'query.txt').read_text(encoding='utf-8').splitlines()
            self.assertEqual([json.loads(line) for line in lines], [records[0]['query'],None,None])
