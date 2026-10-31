"""Compile the shared logical query to fixed SQL with bound JSON paths/values."""
import json
from dataclasses import dataclass


@dataclass(frozen=True)
class SQLStatement:
    sql: str
    parameters: tuple

    def to_dict(self):
        return {'sql': self.sql, 'parameters': list(self.parameters)}


def field_path(field):
    return '$.' + json.dumps(field, ensure_ascii=False)


def equality_clause(query):
    """
    Example query:
    
    SELECT *
    FROM kb_records AS r
    WHERE r.collection = ?
    AND r.entity_id IS ?
    AND (
      json_type(r.document, ?) IS NOT NULL
      AND json_extract(r.document, ?) IS ?
    )
    AND (
      json_type(r.document, ?) IS NOT NULL
      AND json_extract(r.document, ?) IS ?
    );
    
    """
    
    clauses, values = ['r.collection = ?'], [query['collection']]
    
    for field, value in query['filters'].items():
        if field == 'id':
            clauses.append('r.entity_id IS ?')
            values.append(value)
        else:
            path = field_path(field) # $.feild
            clauses.append('(json_type(r.document, ?) IS NOT NULL AND json_extract(r.document, ?) IS ?)')
            values.extend((path, path, value))
            
    return clauses, values


def membership_clause(condition):
    """
    Example Query:

    SELECT *
    FROM kb_records AS r
    WHERE (
    json_type(r.document, ?) = 'array'

    AND NOT EXISTS (
        SELECT 1
        FROM json_each(?) AS wanted
        WHERE NOT EXISTS (
            SELECT 1
            FROM json_each(r.document, '$.skills') AS a
            WHERE a.value = wanted.value
        )
    )
    );
    
    """
    
    path = field_path(condition['field'])
    value, operator = condition['value'], condition['operator']
    if operator == 'contains':
        return ('EXISTS (SELECT 1 FROM json_each(r.document, ?) AS a WHERE a.value = ?)', [path, value])
    if operator == 'contains_any':
        return ('''EXISTS (SELECT 1 FROM json_each(r.document, ?) AS a
                   JOIN json_each(?) AS wanted ON a.value = wanted.value)''',
                [path, json.dumps(value, ensure_ascii=False)])
    # contains_all. Missing arrays must not satisfy the predicate vacuously.
    return ('''(json_type(r.document, ?) = 'array' AND NOT EXISTS (
                SELECT 1 FROM json_each(?) AS wanted WHERE NOT EXISTS (
                    SELECT 1 FROM json_each(r.document, ?) AS a WHERE a.value = wanted.value)))''',
            [path, json.dumps(value, ensure_ascii=False), path])


def compile_query(query) -> SQLStatement:
    clauses, values = equality_clause(query)
    
    for condition in query.get('conditions', []):
        clause, parameters = membership_clause(condition)
        clauses.append(clause)
        values.extend(parameters)
        
    return SQLStatement('SELECT r.document FROM kb_records AS r WHERE ' +
                        ' AND '.join(clauses) + ' ORDER BY r.position', tuple(values))
