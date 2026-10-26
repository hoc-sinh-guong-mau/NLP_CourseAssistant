"""Read-only SQLite KB implementing the JSON backend's execute(query) contract."""
import json
from pathlib import Path
import sqlite3

from src.config import SQLITE_PATH
from src.retrieval.exceptions import KnowledgeBaseError
from src.retrieval.query_contract import validate_query, project_record
from .compiler import compile_query, equality_clause, field_path, membership_clause
from .storage import open_snapshot


class SQLiteKnowledgeBase:
    def __init__(self, database=SQLITE_PATH):
        self.database = Path(database)
        connection = open_snapshot(self.database)
        try:
            self.collection_names = {row[0] for row in connection.execute('SELECT name FROM kb_collections')}
        except sqlite3.Error as exc:
            raise KnowledgeBaseError('Invalid SQLite collection catalog') from exc
        finally:
            connection.close()

    def compile(self, query):
        validate_query(query, self.collection_names)
        return compile_query(query)

    def execute(self, query):
        statement = self.compile(query)
        connection = open_snapshot(self.database)
        try:
            # Match JSON's error for a present scalar used as an array field.
            clauses, values = equality_clause(query)
            for condition in query.get('conditions', []):
                path = field_path(condition['field'])
                invalid = connection.execute(
                    'SELECT r.entity_id FROM kb_records AS r WHERE ' + ' AND '.join(clauses) +
                    " AND json_type(r.document, ?) IS NOT NULL AND json_type(r.document, ?) != 'array' LIMIT 1",
                    (*values, path, path),
                ).fetchone()
                if invalid:
                    raise KnowledgeBaseError('Membership field must be a list', context={
                        'id':invalid[0], 'field':condition['field'],
                    })
                clause, parameters = membership_clause(condition)
                clauses.append(clause)
                values.extend(parameters)
            return [project_record(json.loads(row[0]), query)
                    for row in connection.execute(statement.sql, statement.parameters)]
        except (sqlite3.Error, json.JSONDecodeError) as exc:
            raise KnowledgeBaseError('SQLite query execution failed', context={'path':str(self.database)}) from exc
        finally:
            connection.close()
