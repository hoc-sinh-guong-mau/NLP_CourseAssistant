"""Typed local references are rewritten to existing business semantic frames."""
from src.semantic import SemanticFrame
from .exceptions import ContextResolutionError


def single(state, kind):
    ids = state.entities.get(kind, [])
    if len(ids) != 1:
        raise ContextResolutionError('Cần một thực thể phù hợp trong ngữ cảnh; chưa có hoặc có nhiều ứng viên.',
                                     context={'entity_type':kind,'candidates':list(ids)})
    return ids[0]


class ContextResolver:
    def __init__(self, state, kb):
        self.state, self.kb = state, kb

    def resolve(self, frame):
        state=self.state
        qtype=frame.qtype
        if qtype=='PART_OUTPUT':
            args={'part_id':single(state,'assignment_part'),'assignment_id':single(state,'assignment')}
            return SemanticFrame('GET_ASSIGNMENT',args,'PART_OUTPUTS')
        if qtype=='RELATED_TOPIC':
            return SemanticFrame('GET_TOPIC',{'chapter_id':single(state,'chapter'),
                                             'topic_id':frame.arguments['topic_id']},'CHAPTER_HAS_TOPIC')
        if qtype=='NEXT_CHAPTER':
            current=single(state,'chapter')
            rows=self.kb.execute({'collection':'chapters','filters':{'id':current}})
            if not rows: raise ContextResolutionError('Chương trong ngữ cảnh không có trong KB.')
            candidates=self.kb.execute({'collection':'chapters','filters':{
                'number':rows[0]['number']+1,'course_id':rows[0]['course_id']}})
            if len(candidates)!=1:
                raise ContextResolutionError('Chưa có một chương tiếp theo được xác định trong KB.')
            return SemanticFrame('GET_TOPIC',{'chapter_id':candidates[0]['id']},'CHAPTER_CONTENT')
        if qtype=='COURSE_CHAPTER_COUNT':
            return SemanticFrame('GET_COURSE_INFO',{'course_id':single(state,'course')},'CHAPTER_COUNT')
        if qtype in {'CHAPTER_RESOURCE','RELATED_RESOURCE'}:
            if qtype=='RELATED_RESOURCE' and state.focus=='topic':
                return SemanticFrame('GET_RESOURCE',{'topic_id':single(state,'topic')},'RESOURCE_BY_TOPIC')
            return SemanticFrame('GET_RESOURCE',{'chapter_id':single(state,'chapter')},'RESOURCE_BY_CHAPTER')
        if qtype=='CONTENT_CHAPTER':
            if state.focus=='learning_outcome':
                return SemanticFrame('GET_TOPIC',{'learning_outcome_id':single(state,'learning_outcome')},'FIND_CHAPTER_BY_LO')
            return SemanticFrame('GET_TOPIC',{'topic_id':single(state,'topic')},'FIND_CHAPTER_BY_TOPIC')
        raise ContextResolutionError('Chưa có quy tắc giải quyết kiểu tham chiếu này.',context={'qtype':qtype})
