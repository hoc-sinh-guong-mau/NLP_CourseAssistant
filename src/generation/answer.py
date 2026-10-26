"""Dispatch grounded answers; handler configuration is independent of pipeline."""
from .exceptions import UnsupportedAnswerError
from .formatting import display, label, missing, present, qualify
from .templates import FIELD_TEMPLATES
from . import handlers as domain


def field_handler(template):
    def render(frame, records):
        if not records or not present(records[0].get(template.field)):
            return missing()
        row=records[0]
        return 'ok',template.text.format(entity=label(frame,row,template.slot),value=display(row[template.field]))
    return render


def build_handlers():
    handlers={key:field_handler(template) for key,template in FIELD_TEMPLATES.items()}
    groups=[
        ('GET_COURSE_INFO','CHAPTER_COUNT MAIN_PARTS ASSESSMENT LEARNING_OUTCOMES',domain.course_list),
        ('GET_COURSE_INFO','EXAM_OPEN_BOOK',domain.exam_open_book),
        ('GET_SCHEDULE','WEEK_CONTENT WEEK_CHAPTER CHAPTER_WEEK PART_WEEKS TOPIC_WEEK TOPICS_WEEK',domain.schedule),
        ('GET_TOPIC','FIND_CHAPTER_BY_LO FIND_CHAPTER_BY_TOPIC FIND_CHAPTER_BY_TOPICS CHAPTER_CONTENT CHAPTER_METHODS CHAPTER_HAS_TOPIC',domain.chapter),
        ('GET_ASSIGNMENT','TEAM_SIZE ASSIGNMENT_LIST HAS_COMPONENT REQUIREMENTS OUTPUTS PART_OUTPUTS PART_INFO PART_REQUIREMENTS',domain.assignment),
        ('GET_DEADLINE','DEADLINE',domain.deadline),
        ('GET_RESOURCE','RESOURCE_AUTHOR RESOURCE_BY_CHAPTER RESOURCE_BY_TOPIC RESOURCE_BY_CATEGORY TEXTBOOK_LIST REFERENCE_LIST',domain.resource),
        ('GET_RULE','PERMISSION RULE_INFO',domain.policy),
        ('GET_LO','LO_INFO LO_CONTENT',domain.learning_outcome),
        ('GET_INSTRUCTOR','INSTRUCTOR',domain.instructor),
    ]
    for intent,qtypes,handler in groups:
        for qtype in qtypes.split():
            handlers[intent,qtype]=handler
    return handlers


ANSWER_HANDLERS=build_handlers()


class AnswerGenerator:
    def __init__(self, handlers=None):
        self._custom = handlers is not None
        # Preserve the existing custom-handler API handler(records).
        self.handlers = dict(ANSWER_HANDLERS) if handlers is None else {
            key:(lambda frame, records, callback=callback: callback(records))
            for key,callback in handlers.items()
        }

    def render(self, frame, records):
        key=(frame.predicate,frame.qtype)
        if key not in self.handlers:
            raise UnsupportedAnswerError(f'Unsupported answer template: {key}')
        status,text=self.handlers[key](frame,records)
        if not self._custom and (status=='ok' or (frame.predicate=='GET_RULE' and records)):
            text=qualify(records,text)
        return status,text
