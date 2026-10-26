import json
from copy import deepcopy
from pathlib import Path

from src.common.files import read_text
from src.config import KB_DIR

from .exceptions import KnowledgeBaseError, QueryError


class KnowledgeBase:
    def __init__(self, directory=KB_DIR):
        self.collections = {}
        directory = Path(directory)
        paths = sorted(directory.glob("*.json"))
        if not paths:
            raise KnowledgeBaseError(f"No JSON collections in {directory}")
        for path in paths:
            name = path.stem
            try:
                rows = json.loads(read_text(path, KnowledgeBaseError))
            except json.JSONDecodeError as exc:
                raise KnowledgeBaseError("Invalid JSON collection", context={"path": str(path)}) from exc
            if not isinstance(rows, list) or any(not isinstance(row, dict) or not isinstance(row.get("id"), str) or not row["id"] for row in rows):
                raise KnowledgeBaseError(f"{path} must contain a list of records with IDs")
            if len({row["id"] for row in rows}) != len(rows):
                raise KnowledgeBaseError(f"Duplicate IDs in {path}")
            self.collections[name] = rows

    def _validate_query(self, query):
        if not isinstance(query, dict) or set(query) - {'collection','filters','select','conditions','context'}:
            raise QueryError('Query must be a mapping with supported fields')
        if not isinstance(query.get('collection'), str) or query['collection'] not in self.collections:
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

    @staticmethod
    def _matches(row, condition):
        field, operator, value = condition['field'], condition['operator'], condition['value']
        if field not in row:
            return False
        actual = row[field]
        if not isinstance(actual,list):
            raise KnowledgeBaseError('Membership field must be a list', context={'id':row['id'],'field':field})
        if operator == 'contains':
            return value in actual
        if operator == 'contains_all':
            return all(item in actual for item in value)
        return any(item in actual for item in value)

    def execute(self, query):
        self._validate_query(query)
        result = []
        for row in self.collections[query['collection']]:
            if not all(key in row and row[key] == value for key,value in query['filters'].items()):
                continue
            if not all(self._matches(row,c) for c in query.get('conditions',[])):
                continue
            if 'select' not in query:
                selected = row
            else:
                # Preserve identity/provenance and display labels for rendering.
                metadata = ('id','name','title','source','source_section','is_sample')
                selected = {field:row[field] for field in metadata if field in row}
                selected.update({field:row.get(field) for field in query['select']})
            result.append(deepcopy(selected))
        return result
