import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from src.application.pipeline import CourseAssistant
from src.config import DATA_DIR, LEXICON_DIR, ROOT
from src.lexical import Lexicon
from src.retrieval import KnowledgeBase, KnowledgeBaseError
from src.retrieval.normalization import build_collections, normalize_kb, validate_collections
from src.retrieval.normalization.builder import quality_notes


class KBNormalizationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = build_collections()

    def test_source_facts_and_multiline_fields(self):
        course = self.data['course'][0]
        self.assertEqual(course['credits'], 3)
        self.assertIn('ngôn ngữ tự nhiên', course['description'])
        self.assertIn('ứng dụng cụ thể', course['objectives'])
        self.assertEqual({e['id']: e['duration_minutes'] for e in self.data['exams']}, {'MIDTERM':60, 'FINAL':90})
        self.assertEqual(sum(row['weight_percent'] for row in self.data['assessment_items']), 100)
        self.assertEqual(len(self.data['chapters']), 12)
        self.assertEqual(len(self.data['schedule']), 15)
        self.assertEqual(len(self.data['learning_outcomes']), 16)
        lo4 = next(row for row in self.data['learning_outcomes'] if row['id'] == 'LO4')
        self.assertIn('hỏi đáp đơn giản', lo4['description'])
        self.assertEqual(next(row for row in self.data['learning_outcomes'] if row['id']=='LO2.5')['parent_id'], 'LO2')

    def test_one_assignment_and_no_fabricated_deadline_or_instructor(self):
        self.assertEqual([row['id'] for row in self.data['assignments']], ['BTL01'])
        assignment = self.data['assignments'][0]
        self.assertIsNone(assignment['deadline'])
        self.assertEqual(assignment['team_size'], {'min':3,'max':4})
        self.assertEqual(assignment['part_ids'], ['PART_I','PART_II','PART_III','PART_IV'])
        self.assertEqual([m['week_id'] for m in assignment['milestones']], ['WEEK_08','WEEK_12','WEEK_15'])
        self.assertTrue(all(m['date'] is None for m in assignment['milestones']))
        self.assertEqual(self.data['instructors'], [])

    def test_partial_topic_links_have_evidence_and_reverse_links(self):
        topics = {row['id']: row for row in self.data['topics']}
        self.assertEqual(topics['PCFG']['chapter_ids'], ['CH03','CH06'])
        self.assertNotIn('CH06', topics['CFG']['chapter_ids'])
        chapters = {row['id']: row for row in self.data['chapters']}
        self.assertIn('QUESTION_ANSWERING', chapters['CH11']['topic_ids'])
        for row in self.data['chapters'] + self.data['schedule']:
            self.assertFalse(row['topic_links_complete'])
            self.assertEqual(set(row['topic_ids']), set(row['topic_evidence']))
            self.assertTrue(all(row['topic_evidence'].values()))
        self.assertEqual(self.data['schedule'][2]['chapter_ids'], ['CH03'])
        self.assertIn('PCFG', self.data['schedule'][6]['topic_ids'])

    def test_sample_flags_and_source_paths(self):
        for name, rows in self.data.items():
            for row in rows:
                self.assertTrue((ROOT / row['source']).is_file(), (name,row['id']))
                self.assertTrue(row['source_section'])
        for name in ('schedule','assignments','assignment_parts','policies'):
            self.assertTrue(all(row['is_sample'] for row in self.data[name]))
        self.assertNotIn('SYNTHETIC_DEMO_ONLY', json.dumps(self.data))

    def test_lexicon_entity_ids_resolve_to_kb(self):
        categories = {'COURSE':'course','COURSE_PART':'course_parts','EXAM':'exams',
                      'ASSESSMENT_ITEM':'assessment_items','WEEK':'schedule','CHAPTER':'chapters',
                      'TOPIC':'topics','PART':'assignment_parts','ASSIGNMENT_COMPONENT':'assignment_parts',
                      'ASSIGNMENT_NAME':'assignments','RESOURCE_TITLE':'resources',
                      'RESOURCE_TOPIC':'resource_categories','LO_ID':'learning_outcomes',
                      'RULE_SUBJECT':'policies','RULE_ACTION':'policies','USE_SUBJECT':'policies',
                      'OBLIGATION_ACTION':'policies'}
        indexes = {name:{row['id'] for row in rows} for name,rows in self.data.items()}
        for entry in Lexicon.load(LEXICON_DIR).entries:
            if entry.category in categories:
                self.assertIn(entry.canonical_id, indexes[categories[entry.category]])

    def test_resources_preserve_missing_values(self):
        resources = {row['id']:row for row in self.data['resources']}
        self.assertEqual(len(resources), 8)
        self.assertEqual(resources['REFERENCE_2']['authors'], ['Steven Bird','Ewan Klein','Edward Loper'])
        self.assertEqual(resources['REFERENCE_2']['category_ids'], ['PYTHON_NLP'])
        self.assertIsNone(resources['REFERENCE_5']['year'])
        self.assertEqual(resources['REFERENCE_5']['authors'], [])
        self.assertTrue(all(not row['topic_links_complete'] for row in resources.values()))

    def test_rejects_dangling_links_duplicate_ids_and_missing_provenance(self):
        for change in ('dangling','duplicate','provenance'):
            data = copy.deepcopy(self.data)
            if change == 'dangling': data['schedule'][0]['chapter_ids'] = ['CH99']
            elif change == 'duplicate': data['course'].append(copy.deepcopy(data['course'][0]))
            else: del data['course'][0]['source']
            with self.subTest(change=change), self.assertRaises(KnowledgeBaseError):
                validate_collections(data)

    def test_rebuild_is_deterministic_and_keeps_source_and_sqlite_unchanged(self):
        originals = {p:hashlib.sha256(p.read_bytes()).hexdigest() for p in (DATA_DIR/'raw').iterdir() if p.is_file()}
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            sqlite = output/'course_assistant.sqlite3'
            sqlite.write_bytes(b'untouched sqlite fixture')
            counts = normalize_kb(output_dir=output)
            first = {p.name:p.read_bytes() for p in output.glob('*.json')}
            normalize_kb(output_dir=output)
            self.assertEqual(first, {p.name:p.read_bytes() for p in output.glob('*.json')})
            self.assertEqual(sqlite.read_bytes(), b'untouched sqlite fixture')
            self.assertEqual(len(counts), 14)
            self.assertEqual(KnowledgeBase(output).collections, self.data)
        self.assertEqual(originals, {p:hashlib.sha256(p.read_bytes()).hexdigest() for p in originals})

    def test_missing_source_does_not_overwrite_existing_db(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            existing = root/'db/course.json'
            existing.parent.mkdir()
            existing.write_text('previous dataset', encoding='utf-8')
            with self.assertRaises(KnowledgeBaseError):
                normalize_kb(raw_dir=root/'missing', output_dir=existing.parent)
            self.assertEqual(existing.read_text(), 'previous dataset')

    def test_source_inconsistency_reported_without_changing_values(self):
        notes = {note['code']:note for note in quality_notes(self.data)}
        self.assertEqual(notes['SOURCE_HOURS_MISMATCH']['reported_total'], 150)
        self.assertEqual(notes['SOURCE_HOURS_MISMATCH']['component_sum'], 135)
        self.assertIn('DEADLINE_NOT_PROVIDED', notes)

    def test_deadline_pipeline_handles_missing_and_known_values(self):
        self.assertEqual(CourseAssistant().process('Deadline btl là khi nào?')['status'], 'missing_information')
        kb = Mock()
        kb.execute.return_value = [{'id':'BTL01','name':'bài tập lớn','deadline':'TEST_DATE'}]
        record = CourseAssistant(kb=kb).process('Deadline btl là khi nào?')
        self.assertEqual(record['status'], 'ok')
        self.assertIn('TEST_DATE', record['answer'])
