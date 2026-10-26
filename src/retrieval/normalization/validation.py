"""Validate normalized IDs, provenance and referential integrity before export."""
from src.retrieval.exceptions import KnowledgeBaseError

# (collection, field, referenced collection, is-list)
RELATIONS = (
    ('course', 'part_ids', 'course_parts', True),
    ('course', 'learning_outcome_ids', 'learning_outcomes', True),
    ('course', 'instructor_ids', 'instructors', True),
    ('chapters', 'topic_ids', 'topics', True),
    ('chapters', 'course_part_id', 'course_parts', False),
    ('topics', 'chapter_ids', 'chapters', True),
    ('schedule', 'chapter_ids', 'chapters', True),
    ('schedule', 'topic_ids', 'topics', True),
    ('schedule', 'course_part_id', 'course_parts', False),
    ('assignments', 'part_ids', 'assignment_parts', True),
    ('assignment_parts', 'assignment_id', 'assignments', False),
    ('learning_outcomes', 'parent_id', 'learning_outcomes', False),
    ('learning_outcomes', 'chapter_ids', 'chapters', True),
    ('learning_outcomes', 'topic_ids', 'topics', True),
    ('resources', 'category_ids', 'resource_categories', True),
    ('resources', 'topic_ids', 'topics', True),
)


def validate_collections(collections):
    indexes = {}
    for name, records in collections.items():
        ids = []
        if not isinstance(records, list):
            raise KnowledgeBaseError('Collection must be a list', context={'collection': name})
        for row in records:
            if not isinstance(row, dict) or not isinstance(row.get('id'), str) or not row['id']:
                raise KnowledgeBaseError('Record needs a nonempty ID', context={'collection': name})
            if not row.get('source') or not row.get('source_section') or not isinstance(row.get('is_sample'), bool):
                raise KnowledgeBaseError('Missing provenance', context={'collection': name, 'id': row['id']})
            ids.append(row['id'])
        if len(ids) != len(set(ids)):
            raise KnowledgeBaseError('Duplicate canonical IDs', context={'collection': name})
        indexes[name] = set(ids)
    for name, records in collections.items():
        for row in records:
            if 'course_id' in row and row['course_id'] not in indexes['course']:
                raise KnowledgeBaseError('Unknown course ID', context={'collection': name, 'id': row['id']})
    for collection, field, target, multiple in RELATIONS:
        for row in collections[collection]:
            value = row.get(field)
            if value is None and not multiple:
                if (collection, field) in {
                    ('chapters', 'course_part_id'), ('schedule', 'course_part_id'),
                    ('learning_outcomes', 'parent_id'),
                }:
                    continue
                raise KnowledgeBaseError('Missing required relation', context={'collection': collection, 'id': row['id'], 'field': field})
            if multiple and not isinstance(value, list):
                raise KnowledgeBaseError('Relation must be a list', context={'collection': collection, 'id': row['id'], 'field': field})
            for entity in value if multiple else [value]:
                if not isinstance(entity, str) or entity not in indexes[target]:
                    raise KnowledgeBaseError('Dangling KB reference', context={
                        'collection': collection, 'id': row['id'], 'field': field, 'target': entity,
                    })
    for chapter in collections['chapters']:
        for topic in chapter['topic_ids']:
            reverse = next(row for row in collections['topics'] if row['id'] == topic)
            if chapter['id'] not in reverse['chapter_ids']:
                raise KnowledgeBaseError('Inconsistent chapter-topic reverse relation')
    if sum(row['weight_percent'] for row in collections['assessment_items']) != 100:
        raise KnowledgeBaseError('Assessment weights must sum to 100')
    for assignment in collections['assignments']:
        for milestone in assignment.get('milestones', []):
            if milestone['week_id'] not in indexes['schedule']:
                raise KnowledgeBaseError('Milestone refers to an unknown week')
