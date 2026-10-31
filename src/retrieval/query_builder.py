"""Translate semantic slots to a whitelisted, serializable KB query."""
from src.semantic.models import SemanticFrame

from .exceptions import QueryError, UnsupportedQueryError
from .models import QuerySpec
from .query_rules import QUERY_SPECS


def require_slot(frame, slot, *, multiple=False):
    value = frame.arguments.get(slot)
    valid = (isinstance(value, list) and bool(value) and all(isinstance(v, str) and v.strip() for v in value)
             if multiple else isinstance(value, str) and bool(value.strip()))
    if not valid:
        raise QueryError('Missing or invalid semantic argument', context={
            'slot': slot, 'intent': frame.predicate, 'qtype': frame.qtype,
        })
    return list(value) if multiple else value


class QueryBuilder:
    def __init__(self, specs=None):
        self.specs = dict(QUERY_SPECS if specs is None else specs)

    def build(self, frame: SemanticFrame):
        """
        Build Querry from Semantic Frame
        :args:
        @frame: Semantic Frame
        
        :return:
        @querry: dict
        
        """
        
        key = (frame.predicate, frame.qtype)
        
        if key not in self.specs:
            raise UnsupportedQueryError(f'Unsupported query: {key}')

        # Extract from Specs
        spec = self.specs[key]
        
        filters = {field: require_slot(frame, slot) for field, slot in spec.filters}
        
        for field, value in spec.constants:
            if field in filters:
                raise QueryError('Conflicting query filters', context={'field':field})
            filters[field] = value

        # Build Querry
            
        query = {'collection':spec.collection, 'filters':filters, 'select':list(spec.select)}
        if spec.conditions:
            query['conditions'] = [
                {'field': condition.field, 'operator': condition.operator,
                 'value': require_slot(frame, condition.slot, multiple=condition.operator in {'contains_all','contains_any'})}
                for condition in spec.conditions
            ]

        # Additional Context

        if spec.optional_context or spec.required_context:
            context = {slot:require_slot(frame, slot) for slot in spec.required_context}
            context.update({slot:require_slot(frame, slot) for slot in spec.optional_context if slot in frame.arguments})
            if context:
                query['context'] = context

        return query
