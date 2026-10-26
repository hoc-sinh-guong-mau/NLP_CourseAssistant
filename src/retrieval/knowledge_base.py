import json
from pathlib import Path

from src.common.files import read_text
from src.config import KB_DIR

from .exceptions import KnowledgeBaseError
from .query_contract import validate_query, project_record


class KnowledgeBase:
    def __init__(self, directory=None):
        # In-memory reference executor for tests; production uses SQLite.
        if directory is None:
            from .normalization import build_collections
            self.collections = build_collections()
            return
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
        validate_query(query, self.collections)
        result = []
        for row in self.collections[query['collection']]:
            if not all(key in row and row[key] == value for key,value in query['filters'].items()):
                continue
            if not all(self._matches(row,c) for c in query.get('conditions',[])):
                continue
            result.append(project_record(row, query))
        return result
