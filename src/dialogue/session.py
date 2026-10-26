"""One independent context per conversation; never read entities from answer text."""
from copy import deepcopy

from src.common import run_stage
from .models import ContextState
from .resolver import ContextResolver

SLOT_TYPES={'course_id':'course','week_id':'week','chapter_id':'chapter',
            'assignment_id':'assignment','part_id':'assignment_part','component_id':'assignment_part',
            'topic_id':'topic','topic_ids':'topic','learning_outcome_id':'learning_outcome'}
COLLECTIONS={'course':'course','week':'schedule','chapter':'chapters','assignment':'assignments',
             'assignment_part':'assignment_parts','topic':'topics','learning_outcome':'learning_outcomes'}


class DialogueSession:
    def __init__(self, assistant):
        self.assistant=assistant
        self.reset()

    def reset(self):
        self.state=ContextState()
        self.turn=0

    def _remember(self, record):
        frame=record['semantic']
        entities={}
        def add(kind,values):
            if isinstance(values,str): values=[values]
            for value in values:
                if value not in entities.setdefault(kind,[]):entities[kind].append(value)
        for slot,value in frame['arguments'].items():
            if slot in SLOT_TYPES:add(SLOT_TYPES[slot],value)
        # Parent/course relationships are fetched by ID, not inferred from ID spelling.
        for kind,ids in list(entities.items()):
            for entity in ids:
                rows=run_stage('knowledge_base',self.assistant.kb.execute,
                               {'collection':COLLECTIONS[kind],'filters':{'id':entity}})
                for row in rows:
                    if row.get('course_id'):add('course',row['course_id'])
                    if kind=='assignment_part' and row.get('assignment_id'):add('assignment',row['assignment_id'])
                    if kind=='week':
                        add('chapter',row.get('chapter_ids',[]))
                        add('topic',row.get('topic_ids',[]))
        intent=frame['predicate']
        focus={'GET_SCHEDULE':'week','GET_TOPIC':'chapter','GET_ASSIGNMENT':'assignment',
               'GET_DEADLINE':'assignment','GET_COURSE_INFO':'course','GET_LO':'learning_outcome'}.get(intent)
        if intent=='GET_ASSIGNMENT' and entities.get('assignment_part'):focus='assignment_part'
        if intent=='GET_TOPIC' and frame['qtype']=='FIND_CHAPTER_BY_LO':focus='learning_outcome'
        # Results may identify a chapter/part that was not explicit in the question.
        if intent=='GET_TOPIC' and frame['qtype']!='FIND_CHAPTER_BY_LO':
            add('chapter',[row['id'] for row in record['result']])
        if intent=='GET_ASSIGNMENT' and frame['qtype']=='HAS_COMPONENT':
            add('assignment_part',[row['id'] for row in record['result']])
        # Resource turns preserve their resolved referent; unrelated turns replace it.
        if intent=='GET_RESOURCE':
            focus='chapter' if entities.get('chapter') else 'topic' if entities.get('topic') else None
        self.state=ContextState(entities,focus,self.turn)

    def process(self, text):
        self.turn+=1
        before=deepcopy(self.state.to_dict())
        used={}
        def resolve(frame):
            used.update(source_turn=self.state.source_turn, entities=deepcopy(self.state.entities))
            resolved=ContextResolver(self.state,self.assistant.kb).resolve(frame)
            used['resolved_arguments']=deepcopy(resolved.arguments)
            return resolved
        record=self.assistant.process(text,resolver=resolve)
        record.update(turn=self.turn,context_before=before,context_used=used)
        # Missing-information answers may still ground an explicit, existing entity
        # (e.g. a LO whose chapter relation is not yet recorded).
        if record['status'] in {'ok','missing_information'} and record['result'] and record['semantic']:
            self._remember(record)
        record['context_after']=deepcopy(self.state.to_dict())
        return record
