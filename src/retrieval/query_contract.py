"""Validation and output contract shared by JSON and SQLite backends."""
from copy import deepcopy
from .exceptions import QueryError


def validate_query(query: dict, collections):
    """
    Validate querry, if not raises error

    :args:
    @query: dict
    """
    
    if not isinstance(query, dict) or set(query) - {'collection','filters','select','conditions','context'}:
        raise QueryError('Query must be a mapping with supported fields')

    if not isinstance(query.get('collection'), str) or query['collection'] not in collections:
        raise QueryError('Unknown KB collection', context={'collection': query.get('collection')})
    
    if not isinstance(query.get('filters'), dict):
        raise QueryError('Query filters must be a mapping')
    
    if any(not isinstance(key,str) or not key or not isinstance(value,(str,int,float,bool,type(None)))
           for key,value in query['filters'].items()):
        raise QueryError('Equality filters require field names and scalar values')
    
    if 'select' in query and (not isinstance(query['select'],list) or
                              any(not isinstance(field,str) or not field for field in query['select'])):
        raise QueryError('Query select must be a list of field names')
    
    if 'context' in query and (not isinstance(query['context'],dict) or
                               any(not isinstance(k,str) or not isinstance(v,str) for k,v in query['context'].items())):
        raise QueryError('Query context must map slot names to IDs')
    
    conditions = query.get('conditions', [])
    
    if not isinstance(conditions,list):
        raise QueryError('Query conditions must be a list')
    
    for condition in conditions:
        if not isinstance(condition,dict) or set(condition) != {'field','operator','value'}:
            raise QueryError('Each condition needs field, operator and value')
        
        field, operator, value = condition['field'], condition['operator'], condition['value']
        
        if not isinstance(field,str) or not field or operator not in ('contains','contains_all','contains_any'):
            raise QueryError('Invalid condition field or unsupported operator')
        
        if operator == 'contains':
            valid = isinstance(value,str) and bool(value.strip())
        else:
            valid = isinstance(value,list) and bool(value) and all(isinstance(v,str) and v.strip() for v in value)
        if not valid:
            raise QueryError('Invalid membership condition value')

def project_record(row, query):
    if 'select' not in query:
        return deepcopy(row)
    metadata = ('id','name','title','source','source_section','is_sample')
    selected = {field:row[field] for field in metadata if field in row}
    selected.update({field:row.get(field) for field in query['select']})
    return deepcopy(selected)
