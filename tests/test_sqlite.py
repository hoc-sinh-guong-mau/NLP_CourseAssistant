import hashlib
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from src.application.pipeline import CourseAssistant
from src.config import KB_DIR, ROOT
from src.retrieval import KnowledgeBase, KnowledgeBaseError, QueryBuilder, QueryError
from src.retrieval.query_rules import QUERY_SPECS
from src.retrieval.sqlite import SQLiteKnowledgeBase, build_sqlite
from src.retrieval.sqlite.storage import open_snapshot, build_snapshot
from src.semantic import SemanticFrame


class SQLiteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory()
        cls.path = Path(cls.temporary.name, 'kb.sqlite3')
        cls.counts = build_sqlite(database=cls.path)
        cls.sql = SQLiteKnowledgeBase(cls.path)
        cls.json = KnowledgeBase()

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def test_all_business_query_specs_match_json(self):
        arguments = {
            'course_id':'CO3085', 'week_id':'WEEK_03', 'chapter_id':'CH03',
            'topic_id':'CFG', 'topic_ids':['CFG','PCFG'], 'course_part_id':'SYNTACTIC_PROCESSING',
            'assignment_id':'BTL01', 'part_id':'PART_I', 'component_id':'PART_I',
            'resource_id':'REFERENCE_2', 'resource_category_id':'PYTHON_NLP',
            'learning_outcome_id':'LO2.5', 'rule_id':'AI_USAGE', 'exam_id':'MIDTERM',
            'assessment_item_id':'MIDTERM',
        }
        builder = QueryBuilder()
        for intent,qtype in QUERY_SPECS:
            with self.subTest(intent=intent,qtype=qtype):
                query = builder.build(SemanticFrame(intent,arguments,qtype))
                self.assertEqual(self.sql.execute(query),self.json.execute(query))

    def test_pipeline_results_match_for_existing_input(self):
        json_app, sql_app = CourseAssistant(kb=self.json), CourseAssistant(kb=self.sql)
        for text in (ROOT/'input/sentences.txt').read_text().splitlines():
            if text.strip():
                with self.subTest(text=text):
                    self.assertEqual(json_app.process(text),sql_app.process(text))

    def test_scalar_null_missing_projection_and_any_match_json(self):
        queries = [
            {'collection':'assignments','filters':{'deadline':None},'select':['deadline','absent']},
            {'collection':'assignments','filters':{'absent':None}},
            {'collection':'exams','filters':{'open_book':True}},
            {'collection':'instructors','filters':{}},
            {'collection':'chapters','filters':{},'conditions':[{'field':'topic_ids','operator':'contains_any','value':['CFG','PCFG']}]},
            {'collection':'chapters','filters':{},'conditions':[{'field':'missing','operator':'contains_all','value':['CFG']}]},
        ]
        for query in queries:
            with self.subTest(query=query):
                self.assertEqual(self.sql.execute(query),self.json.execute(query))

    def test_invalid_queries_and_scalar_membership(self):
        for query in (
            {'collection':'unknown','filters':{}},
            {'collection':'course','filters':{},'conditions':[{'field':'id','operator':'eval','value':'x'}]},
        ):
            with self.assertRaises(QueryError): self.sql.execute(query)
        with self.assertRaises(KnowledgeBaseError):
            self.sql.execute({'collection':'course','filters':{},'conditions':[{'field':'id','operator':'contains','value':'CO3085'}]})

    def test_values_are_bound_and_cannot_inject_sql(self):
        payload = "BTL01' OR 1=1; DROP TABLE kb_records; --"
        query = {'collection':'assignments','filters':{'id':payload}}
        statement = self.sql.compile(query)
        self.assertNotIn(payload,statement.sql)
        self.assertIn(payload,statement.parameters)
        self.assertEqual(self.sql.execute(query),[])
        self.assertEqual(len(self.sql.execute({'collection':'assignments','filters':{}})),1)
        # Field names are bound JSON paths, never SQL identifiers.
        query = {'collection':'course','filters':{"id); DROP TABLE kb_records;--":'x'}}
        self.assertEqual(self.sql.execute(query),[])

    def test_connections_are_read_only(self):
        connection = open_snapshot(self.path)
        try:
            with self.assertRaises(sqlite3.OperationalError):
                connection.execute('DELETE FROM kb_records')
        finally:
            connection.close()

    def test_failed_import_preserves_existing_snapshot_and_legacy_db(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root/'source'
            source.mkdir()
            (source/'course.json').write_text('[{"id":"A"}]')
            snapshot = root/'kb.sqlite3'
            build_snapshot(KnowledgeBase(source).collections,snapshot)
            before = hashlib.sha256(snapshot.read_bytes()).hexdigest()
            (source/'course.json').write_text('[{"id":"A"},{"id":"A"}]')
            with self.assertRaises(KnowledgeBaseError): build_snapshot(KnowledgeBase(source).collections,snapshot)
            self.assertEqual(hashlib.sha256(snapshot.read_bytes()).hexdigest(),before)
            # A serialization failure during insertion must also preserve the old DB.
            (source/'course.json').write_text('[{"id":"A","credits":NaN}]')
            with self.assertRaises(KnowledgeBaseError): build_snapshot(KnowledgeBase(source).collections,snapshot)
            self.assertEqual(hashlib.sha256(snapshot.read_bytes()).hexdigest(),before)
            legacy = root/'legacy.sqlite3'
            conn = sqlite3.connect(legacy)
            conn.execute('CREATE TABLE legacy (id TEXT)')
            conn.close()
            (source/'course.json').write_text('[{"id":"A"}]')
            before = legacy.read_bytes()
            with self.assertRaises(KnowledgeBaseError): build_snapshot(KnowledgeBase(source).collections,legacy)
            self.assertEqual(legacy.read_bytes(),before)
            self.assertEqual(list(root.glob('.kb-*')),[])

    def test_missing_database_does_not_create_empty_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory,'missing.sqlite3')
            with self.assertRaises(KnowledgeBaseError): SQLiteKnowledgeBase(path)
            self.assertFalse(path.exists())

    def test_snapshot_only_changes_on_explicit_rebuild(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root/'source'
            source.mkdir()
            data = source/'course.json'
            data.write_text('[{"id":"A","credits":3}]')
            path = root/'kb.sqlite3'
            build_snapshot(KnowledgeBase(source).collections,path)
            backend = SQLiteKnowledgeBase(path)
            data.write_text('[{"id":"A","credits":4}]')
            query = {'collection':'course','filters':{'id':'A'}}
            self.assertEqual(backend.execute(query)[0]['credits'],3)
            build_snapshot(KnowledgeBase(source).collections,path)
            self.assertEqual(SQLiteKnowledgeBase(path).execute(query)[0]['credits'],4)
