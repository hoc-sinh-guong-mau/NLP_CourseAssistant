"""Semantic schemas shared by paraphrases, independent of surface strings.

Sources are root features, or CATEGORY.FEATURE for a bound lexical subtree.
A tuple of sources produces a list-valued slot (e.g. coordinated topics).
"""
from .exceptions import InvalidSemanticError
from .models import RuleKey, SemanticRule


def build_rules() -> dict[RuleKey, SemanticRule]:
    rules = {}

    def group(intent, qtypes, slots, optional=None):
        for qtype in qtypes.split():
            key = (intent, qtype)
            if key in rules:
                raise InvalidSemanticError(f"Duplicate semantic rule: {key}")
            rules[key] = SemanticRule(dict(slots), dict(optional or {}))

    group('GET_COURSE_INFO', '''CREDITS MAIN_PARTS COURSE_ID COURSE_NAME SEMESTER ECTS
        COURSE_TYPE DEPARTMENT FORMAT DURATION_WEEKS TOTAL_HOURS LECTURE_HOURS
        ASSIGNMENT_HOURS SELF_STUDY_HOURS DESCRIPTION OBJECTIVES ASSESSMENT LEARNING_OUTCOMES''',
        {'course_id': 'ENTITY'})
    group('GET_COURSE_INFO', 'EXAM_DURATION EXAM_FORMAT EXAM_OPEN_BOOK', {'exam_id': 'ENTITY'})
    group('GET_COURSE_INFO', 'ASSESSMENT_WEIGHT', {'assessment_item_id': 'ENTITY'})
    group('GET_SCHEDULE', 'WEEK_CONTENT WEEK_CHAPTER WEEK_ACTIVITY WEEK_MILESTONE', {'week_id': 'ENTITY'})
    group('GET_SCHEDULE', 'CHAPTER_WEEK', {'chapter_id': 'ENTITY'})
    group('GET_SCHEDULE', 'TOPIC_WEEK', {'topic_id': 'ENTITY'})
    group('GET_SCHEDULE', 'TOPICS_WEEK', {'topic_ids': ('ENTITY', 'TARGET')})
    group('GET_SCHEDULE', 'PART_WEEKS', {'course_part_id': 'ENTITY'})
    group('GET_TOPIC', 'FIND_CHAPTER_BY_TOPIC', {'topic_id': 'ENTITY'})
    group('GET_TOPIC', 'FIND_CHAPTER_BY_TOPICS', {'topic_ids': ('ENTITY', 'TARGET')})
    group('GET_TOPIC', 'CHAPTER_CONTENT CHAPTER_METHODS', {'chapter_id': 'ENTITY'})
    group('GET_TOPIC', 'CHAPTER_HAS_TOPIC', {'chapter_id': 'ENTITY', 'topic_id': 'TARGET'})
    group('GET_ASSIGNMENT', 'REQUIREMENTS TEAM_SIZE TITLE GOAL DOMAIN OUTPUTS', {'assignment_id': 'ENTITY'})
    group('GET_ASSIGNMENT', 'ASSIGNMENT_LIST', {'course_id': 'ENTITY'})
    group('GET_ASSIGNMENT', 'PART_INFO PART_OUTPUTS PART_REQUIREMENTS',
          {'part_id': 'ENTITY', 'assignment_id': 'ASSIGNMENT_NAME.ENTITY'})
    group('GET_ASSIGNMENT', 'HAS_COMPONENT',
          {'component_id': 'ENTITY', 'assignment_id': 'ASSIGNMENT_NAME.ENTITY'})
    group('GET_DEADLINE', 'DEADLINE', {'assignment_id': 'ENTITY'})
    group('GET_RESOURCE', 'RESOURCE_BY_CATEGORY', {'resource_category_id': 'ENTITY'})
    group('GET_RESOURCE', 'RESOURCE_BY_TOPIC', {'topic_id': 'ENTITY'})
    group('GET_RESOURCE', 'TEXTBOOK_LIST REFERENCE_LIST', {'course_id': 'ENTITY'})
    group('GET_RESOURCE', 'RESOURCE_AUTHOR RESOURCE_YEAR', {'resource_id': 'ENTITY'})
    group('GET_INSTRUCTOR', 'INSTRUCTOR', {'course_id': 'ENTITY'})
    group('GET_RULE', 'PERMISSION RULE_INFO', {'rule_id': 'ENTITY'}, {'assignment_id': 'TARGET'})
    group('GET_LO', 'LO_INFO LO_CONTENT', {'learning_outcome_id': 'ENTITY'})
    group('CONTEXT_DEPENDENT', 'NEXT_CHAPTER PART_OUTPUT CHAPTER_RESOURCE CONTENT_CHAPTER',
          {'context_ref': 'ENTITY'})
    group('CONTEXT_DEPENDENT', 'RELATED_TOPIC', {'context_ref': 'ENTITY', 'topic_id': 'TARGET'})
    return rules


SEMANTIC_RULES = build_rules()
