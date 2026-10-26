"""Rebuild source-backed JSON collections; never use FAQ answers as facts."""
import json
import re
from pathlib import Path

from src.common.files import write_text
from src.config import RAW_DIR, KB_DIR, LEXICON_DIR
from src.lexical import Lexicon
from src.preprocessing import normalize
from src.retrieval.exceptions import KnowledgeBaseError
from .readers import blocks, fields, items, paragraph, read_source, required
from .validation import validate_collections

COURSE_ID = 'CO3085'
PART_IDS = {
    'Syntactic Processing': 'SYNTACTIC_PROCESSING',
    'Semantic Interpretation': 'SEMANTIC_INTERPRETATION',
    'Context and World Knowledge': 'CONTEXT_WORLD_KNOWLEDGE',
}
# Explicit spelling variants in source material, not guessed topical relations.
SOURCE_TOPIC_TERMS = {
    'TOP_DOWN_PARSING': ['top-down parser'],
    'BOTTOM_UP_CHART_PARSING': ['bottom-up chart parser'],
    'TOP_DOWN_CHART_PARSING': ['top-down chart parser'],
    'POS_TAGGING': ['part-of-speech tagging'],
}
RESOURCE_TERMS = {
    'STATISTICAL_NLP': ['statistical methods', 'statistical natural language processing'],
    'PYTHON_NLP': ['nlp with python', 'natural language processing with python'],
}


def provenance(filename, section, sample=False):
    return {'source': f'data/raw/{filename}', 'source_section': section, 'is_sample': sample}


def match_entities(text, entries, extra_terms=None):
    """Find source evidence, preferring longer overlapping aliases.

    Links are intentionally partial: an absent textual mention is not evidence
    that a chapter does not cover a topic.
    """
    text = normalize(text)
    candidates = []
    for entry in entries:
        terms = [*entry.aliases, *(extra_terms or {}).get(entry.canonical_id, [])]
        # English source headings use plural grammars/forms/etc.
        terms += [term + 's' for term in terms if term.isascii() and not term.endswith('s')]
        for term in set(terms):
            for match in re.finditer(r'(?<!\w)' + re.escape(normalize(term)) + r'(?!\w)', text):
                candidates.append((match.start(), match.end(), entry.canonical_id, match[0]))
    occupied, evidence = [], {}
    for start, end, entity, mention in sorted(candidates, key=lambda c: (-(c[1] - c[0]), c[0], c[2])):
        if any(start < right and end > left for left, right in occupied):
            continue
        occupied.append((start, end))
        evidence.setdefault(entity, set()).add(mention)
    return {entity: sorted(mentions) for entity, mentions in sorted(evidence.items())}


def build_course(text):
    data = fields(text)
    course = {'id': required(data, 'course_id'), **provenance('course_info.txt', 'course')}
    for key in ('course_name', 'course_name_en', 'semester', 'course_type', 'department', 'format'):
        course[key] = paragraph(required(data, key))
    for key in ('credits', 'ects', 'total_course_hours', 'lecture_hours', 'major_assignment_hours', 'self_study_hours'):
        course[key] = int(required(data, key))
    course['description'] = paragraph(required(data, 'course_description'))
    course['objectives'] = paragraph(required(data, 'Mục tiêu'))
    course['duration_weeks'] = int(re.search(r'(\d+) weeks', course['format'])[1])
    course['lecture_periods_per_week'] = int(re.search(r'(\d+) lecture periods', course['format'])[1])
    course['instructor_ids'] = []  # No instructor identity is provided by this source.
    parts = []
    for line in items(required(data, 'main_parts')):
        _, name = line.split(' - ', 1)
        parts.append({'id': PART_IDS[name], 'course_id': course['id'], 'name': name,
                      **provenance('course_info.txt', 'main_parts')})
    course['part_ids'] = [part['id'] for part in parts]
    outcomes = []
    for section in ('learning_outcomes', 'detailed_learning_outcomes'):
        for match, body in blocks(required(data, section), r'^(LO\d+(?:\.\d+)?) - (.*)$'):
            entity = match[1]
            outcomes.append({'id': entity, 'course_id': course['id'],
                             'parent_id': entity.split('.')[0] if '.' in entity else None,
                             'description': paragraph(match[2] + ' ' + body),
                             'chapter_ids': [], 'topic_ids': [], 'links_complete': False,
                             **provenance('course_info.txt', section)})
    course['learning_outcome_ids'] = [row['id'] for row in outcomes]
    assessments = []
    for source_key, entity in [('class_attention_and_assignments','CLASS_ATTENTION_AND_ASSIGNMENTS'),
                               ('major_assignment','MAJOR_ASSIGNMENT'), ('midterm_exam','MIDTERM'), ('final_exam','FINAL')]:
        assessments.append({'id': entity, 'course_id': course['id'],
                            'weight_percent': int(re.fullmatch(r'(\d+) percent', required(data, source_key))[1]),
                            **provenance('course_info.txt', 'assessment')})
    exams = []
    for key in ('midterm', 'final'):
        value = required(data, key)
        exams.append({'id': key.upper(), 'course_id': course['id'], 'format': value,
                      'duration_minutes': int(re.search(r'(\d+) minutes', value)[1]),
                      'open_book': 'open-book' in value, **provenance('course_info.txt', 'exam_format')})
    return course, parts, outcomes, assessments, exams


def build_chapters(text, topic_entries):
    result = []
    for match, body in blocks(text, r'^CHAPTER (\d+): (.+)$'):
        data = fields(body)
        evidence = match_entities(match[2] + '\n' + body, topic_entries, SOURCE_TOPIC_TERMS)
        result.append({'id': required(data, 'chapter_id'), 'number': int(match[1]), 'title': match[2],
                       'course_id': COURSE_ID, 'part_name': required(data, 'part'),
                       'course_part_id': PART_IDS.get(data['part']),
                       'keywords': [part.strip() for part in required(data, 'keywords').split(',')],
                       'summary': paragraph(required(data, 'summary')), 'subtopics': items(required(data, 'subtopics')),
                       'topic_ids': list(evidence), 'topic_evidence': evidence, 'topic_links_complete': False,
                       **provenance('topics.txt', f'CHAPTER {match[1]}')})
    return result


def build_schedule(text, topic_entries):
    result = []
    for match, body in blocks(text, r'^WEEK (\d+)$'):
        data = fields(body)
        topics = items(required(data, 'topics'))
        evidence = match_entities('\n'.join(topics), topic_entries, SOURCE_TOPIC_TERMS)
        chapter = re.fullmatch(r'Chapter (\d+)', data.get('chapter', ''))
        week = int(match[1])
        row = {'id': f'WEEK_{week:02}', 'course_id': COURSE_ID, 'week': week,
               'part': required(data, 'part'), 'course_part_id': PART_IDS.get(data['part']),
               'chapter_ids': [f'CH{int(chapter[1]):02}'] if chapter else [],
               'topics': topics, 'topic_ids': list(evidence), 'topic_evidence': evidence,
               'topic_links_complete': False, **provenance('schedule.txt', f'WEEK {match[1]}', True)}
        for key in ('chapter', 'activity', 'milestone'):
            if data.get(key):
                row[key] = paragraph(data[key])
        result.append(row)
    return result


def build_assignments(text, schedule):
    header = fields(text.split('PART I -', 1)[0])
    entity = required(header, 'assignment_id')
    sizes = re.fullmatch(r'(\d+)-(\d+) students', required(header, 'team_size'))
    parts = []
    sections = blocks(text, r'^PART (IV|III|II|I) - (.+)$')
    for match, body in sections:
        body = body.split('LLM/RAG EXTENSION', 1)[0]
        data = fields(body)
        requirements = data.get('requirements') or data.get('minimum_requirements') or data.get('optional_or_extension')
        parts.append({'id': f'PART_{match[1]}', 'assignment_id': entity, 'title': match[2],
                      'requirements': items(required({'requirements': requirements or ''}, 'requirements')),
                      'outputs': items(data.get('suggested_outputs', '')), 'optional': match[1] == 'III',
                      **provenance('assignments.txt', f'PART {match[1]}', True)})
    assignment = {'id': entity, 'course_id': COURSE_ID, 'name': 'bài tập lớn',
                  'title': required(header, 'title'), 'domain': required(header, 'domain'),
                  'goal': paragraph(required(header, 'goal')), 'deadline': None,
                  'team_size': {'min': int(sizes[1]), 'max': int(sizes[2])},
                  'part_ids': [row['id'] for row in parts],
                  'outputs': [output for row in parts for output in row['outputs']],
                  'outputs_complete': False,
                  'milestones': [{'week_id': week['id'], 'description': week['milestone'],
                                  'date': None, 'source': week['source']} for week in schedule if week.get('milestone')],
                  **provenance('assignments.txt', 'BTL01', True)}
    extension = fields(text.split('LLM/RAG EXTENSION\n', 1)[1])
    assignment['llm_rag_extension'] = {key: paragraph(value) if key != 'not_required' else items(value)
                                       for key, value in extension.items()}
    return [assignment], parts


def build_resources(text, category_entries):
    resources = []
    for match, body in blocks(text, r'^(TEXTBOOK|REFERENCE) (\d+)$'):
        data = fields(body)
        evidence = match_entities(required(data, 'title') + ' ' + required(data, 'usage'), category_entries, RESOURCE_TERMS)
        resources.append({'id': f'{match[1]}_{match[2]}', 'course_id': COURSE_ID,
                          'kind': match[1].lower(), 'title': required(data, 'title'),
                          'authors': [name.strip() for name in (data.get('authors') or data.get('author') or '').split(';') if name.strip()],
                          'publisher': data.get('publisher'), 'year': int(data['year']) if data.get('year') else None,
                          'usage': required(data, 'usage'), 'category_ids': list(evidence),
                          'category_evidence': evidence, 'topic_ids': [], 'topic_links_complete': False,
                          **provenance('resources.txt', f'{match[1]} {match[2]}')})
    return resources


def parse_source(raw_dir, filename, parser, *args):
    text = read_source(raw_dir, filename)
    try:
        return parser(text, *args)
    except KnowledgeBaseError as exc:
        raise KnowledgeBaseError(exc.message, context={**exc.context, "path": str(raw_dir / filename)}) from exc
    except (ValueError, TypeError, KeyError, IndexError, AttributeError) as exc:
        raise KnowledgeBaseError('Source format does not match normalization rules',
                                 context={'path': str(raw_dir / filename)}) from exc


def build_collections(raw_dir=RAW_DIR, lexicon_dir=LEXICON_DIR):
    raw_dir = Path(raw_dir)
    lexicon = Lexicon.load(lexicon_dir)
    topics = [entry for entry in lexicon.entries if entry.category == 'TOPIC']
    categories = [entry for entry in lexicon.entries if entry.category == 'RESOURCE_TOPIC']
    course, parts, outcomes, assessments, exams = parse_source(raw_dir, 'course_info.txt', build_course)
    chapters = parse_source(raw_dir, 'topics.txt', build_chapters, topics)
    schedule = parse_source(raw_dir, 'schedule.txt', build_schedule, topics)
    assignments, assignment_parts = parse_source(raw_dir, 'assignments.txt', build_assignments, schedule)
    policies = [{'id': key.upper(), 'course_id': COURSE_ID, 'description': paragraph(value),
                 'permission': None, **provenance('regulations.txt', key, True)}
                for key, value in parse_source(raw_dir, 'regulations.txt', fields).items()]
    collections = {
        'course': [course], 'course_parts': parts, 'learning_outcomes': outcomes,
        'assessment_items': assessments, 'exams': exams, 'chapters': chapters, 'schedule': schedule,
        'assignments': assignments, 'assignment_parts': assignment_parts,
        'topics': [{'id': entry.canonical_id, 'name': entry.aliases[0], 'aliases': list(entry.aliases),
                    'chapter_ids': [row['id'] for row in chapters if entry.canonical_id in row['topic_ids']],
                    'source': 'models/lexicon/topics.yaml', 'source_section': entry.canonical_id,
                    'is_sample': False, 'chapter_links_complete': False,
                    'chapter_link_source': 'data/raw/topics.txt'} for entry in topics],
        'resources': parse_source(raw_dir, 'resources.txt', build_resources, categories),
        'resource_categories': [{'id': entry.canonical_id, 'name': entry.aliases[0],
                                 'source': 'models/lexicon/resources.yaml', 'source_section': entry.canonical_id,
                                 'is_sample': False} for entry in categories],
        'policies': policies, 'instructors': [],
    }
    validate_collections(collections)
    return collections


def normalize_kb(raw_dir=RAW_DIR, output_dir=KB_DIR, lexicon_dir=LEXICON_DIR, report_path=None):
    # Parse and validate all collections before touching existing JSON files.
    collections = build_collections(raw_dir, lexicon_dir)
    for name, records in collections.items():
        write_text(Path(output_dir) / f'{name}.json', json.dumps(records, ensure_ascii=False, indent=2) + '\n', KnowledgeBaseError)
    counts = {name: len(records) for name, records in collections.items()}
    if report_path is not None:
        report = {'collections': counts, 'quality_notes': quality_notes(collections)}
        write_text(report_path, json.dumps(report, ensure_ascii=False, indent=2) + '\n', KnowledgeBaseError)
    return counts


def quality_notes(collections):
    """Report source gaps without inventing or silently correcting facts."""
    notes = []
    for course in collections['course']:
        subtotal = sum(course[key] for key in ('lecture_hours', 'major_assignment_hours', 'self_study_hours'))
        if subtotal != course['total_course_hours']:
            notes.append({'code': 'SOURCE_HOURS_MISMATCH', 'id': course['id'],
                          'reported_total': course['total_course_hours'], 'component_sum': subtotal,
                          'source': course['source']})
    if any(row['deadline'] is None for row in collections['assignments']):
        notes.append({'code': 'DEADLINE_NOT_PROVIDED'})
    if not collections['instructors']:
        notes.append({'code': 'INSTRUCTOR_NOT_PROVIDED'})
    notes.append({'code': 'PARTIAL_RELATIONS',
                  'message': 'Chapter/topic links are textual evidence only; LO-chapter and resource-topic links are not supplied by raw sources.'})
    return notes
