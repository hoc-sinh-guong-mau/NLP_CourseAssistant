"""Query mappings for business QTYPEs. Context resolution is a separate step."""
from .exceptions import QueryError
from .models import ConditionSpec, QuerySpec


def build_specs():
    specs = {}

    def add(intent, qtype, collection, slot=None, select=(), *, field='id', conditions=(), constants=(), context=(), required_context=()):
        key = (intent, qtype)
        if key in specs:
            raise QueryError('Duplicate query spec', context={'key': key})
        specs[key] = QuerySpec(collection, ((field, slot),) if slot else (), tuple(select),
                               tuple(conditions), tuple(constants), tuple(context), tuple(required_context))

    course_fields = {
        'CREDITS':'credits', 'COURSE_ID':'id', 'COURSE_NAME':'course_name', 'SEMESTER':'semester',
        'ECTS':'ects', 'COURSE_TYPE':'course_type', 'DEPARTMENT':'department', 'FORMAT':'format',
        'DURATION_WEEKS':'duration_weeks', 'TOTAL_HOURS':'total_course_hours',
        'LECTURE_HOURS':'lecture_hours', 'ASSIGNMENT_HOURS':'major_assignment_hours',
        'SELF_STUDY_HOURS':'self_study_hours', 'DESCRIPTION':'description', 'OBJECTIVES':'objectives',
    }
    for qtype, selected in course_fields.items():
        add('GET_COURSE_INFO', qtype, 'course', 'course_id', [selected])
    add('GET_COURSE_INFO','MAIN_PARTS','course_parts','course_id',['name'],field='course_id')
    add('GET_COURSE_INFO','LEARNING_OUTCOMES','learning_outcomes','course_id',['description','parent_id'],field='course_id')
    add('GET_COURSE_INFO','ASSESSMENT','assessment_items','course_id',['weight_percent'],field='course_id')
    add('GET_COURSE_INFO','ASSESSMENT_WEIGHT','assessment_items','assessment_item_id',['weight_percent'])
    for qtype, selected in {'EXAM_DURATION':'duration_minutes','EXAM_FORMAT':'format','EXAM_OPEN_BOOK':'open_book'}.items():
        add('GET_COURSE_INFO',qtype,'exams','exam_id',[selected])

    for qtype, selected in {
        'WEEK_CONTENT':['topics','topic_ids','chapter_ids','topic_links_complete'],
        'WEEK_CHAPTER':['chapter_ids'], 'WEEK_ACTIVITY':['activity'], 'WEEK_MILESTONE':['milestone'],
    }.items():
        add('GET_SCHEDULE',qtype,'schedule','week_id',['week',*selected])
    add('GET_SCHEDULE','CHAPTER_WEEK','schedule',select=['week','chapter_ids'],
        conditions=[ConditionSpec('chapter_ids','contains','chapter_id')])
    add('GET_SCHEDULE','PART_WEEKS','schedule','course_part_id',['week'],field='course_part_id')
    for qtype, slot, operator in [('TOPIC_WEEK','topic_id','contains'),('TOPICS_WEEK','topic_ids','contains_all')]:
        add('GET_SCHEDULE',qtype,'schedule',select=['week','topic_ids','topic_evidence','topic_links_complete'],
            conditions=[ConditionSpec('topic_ids',operator,slot)])

    for qtype, slot, operator in [('FIND_CHAPTER_BY_TOPIC','topic_id','contains'),('FIND_CHAPTER_BY_TOPICS','topic_ids','contains_all')]:
        add('GET_TOPIC',qtype,'chapters',select=['number','title','topic_ids','topic_evidence','topic_links_complete'],
            conditions=[ConditionSpec('topic_ids',operator,slot)])
    for qtype in ('CHAPTER_CONTENT','CHAPTER_METHODS','CHAPTER_HAS_TOPIC'):
        # Membership questions fetch the parent record, including completeness.
        # A missing link must not become an unsupported "no" answer.
        add('GET_TOPIC',qtype,'chapters','chapter_id',
            ['number','title','summary','subtopics','topic_ids','topic_links_complete'],
            required_context=['topic_id'] if qtype == 'CHAPTER_HAS_TOPIC' else [])

    for qtype, selected in {
        'TEAM_SIZE':'team_size', 'TITLE':'title', 'GOAL':'goal', 'DOMAIN':'domain', 'OUTPUTS':'outputs',
    }.items():
        add('GET_ASSIGNMENT',qtype,'assignments','assignment_id',[selected,'outputs_complete'] if qtype=='OUTPUTS' else [selected])
    add('GET_ASSIGNMENT','REQUIREMENTS','assignment_parts','assignment_id',
        ['title','requirements','optional'],field='assignment_id')
    add('GET_ASSIGNMENT','ASSIGNMENT_LIST','assignments','course_id',['title','deadline'],field='course_id')
    for qtype, selected in {
        'PART_INFO':['title','requirements','outputs','optional'],
        'PART_OUTPUTS':['outputs'], 'PART_REQUIREMENTS':['requirements'], 'HAS_COMPONENT':['title','requirements'],
    }.items():
        slot = 'component_id' if qtype=='HAS_COMPONENT' else 'part_id'
        specs['GET_ASSIGNMENT',qtype] = QuerySpec('assignment_parts',
            (('id',slot),('assignment_id','assignment_id')), tuple(selected))
    add('GET_DEADLINE','DEADLINE','assignments','assignment_id',['deadline'])

    for qtype, field, slot in [('RESOURCE_BY_TOPIC','topic_ids','topic_id'),
                               ('RESOURCE_BY_CATEGORY','category_ids','resource_category_id')]:
        add('GET_RESOURCE',qtype,'resources',select=['title','authors','year','usage','topic_ids','topic_links_complete'],
            conditions=[ConditionSpec(field,'contains',slot)])
    for qtype, kind in [('TEXTBOOK_LIST','textbook'),('REFERENCE_LIST','reference')]:
        add('GET_RESOURCE',qtype,'resources','course_id',['title','authors','year'],
            field='course_id',constants=[('kind',kind)])
    add('GET_RESOURCE','RESOURCE_AUTHOR','resources','resource_id',['authors'])
    add('GET_RESOURCE','RESOURCE_YEAR','resources','resource_id',['year'])
    for qtype in ('PERMISSION','RULE_INFO'):
        add('GET_RULE',qtype,'policies','rule_id',['description','permission'],context=['assignment_id'])
    add('GET_INSTRUCTOR','INSTRUCTOR','instructors','course_id',['name','email'],field='course_id')
    for qtype in ('LO_INFO','LO_CONTENT'):
        add('GET_LO',qtype,'learning_outcomes','learning_outcome_id',
            ['description','parent_id','chapter_ids','topic_ids','links_complete'])
    add('GET_COURSE_INFO','CHAPTER_COUNT','chapters','course_id',['number'],field='course_id')
    add('GET_RESOURCE','RESOURCE_BY_CHAPTER','resources',select=['title','authors','year','topic_links_complete'],
        conditions=[ConditionSpec('chapter_ids','contains','chapter_id')])
    add('GET_TOPIC','FIND_CHAPTER_BY_LO','learning_outcomes','learning_outcome_id',['description','chapter_ids','links_complete'])
    return specs


QUERY_SPECS = build_specs()
