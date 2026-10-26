import json
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

    def execute(self, query):
        if query.get("collection") not in self.collections:
            raise QueryError("Unknown KB collection", context={"collection": query.get("collection")})
        if not isinstance(query.get("filters"), dict):
            raise QueryError("Query filters must be a mapping")
        return [
            row for row in self.collections[query["collection"]]
            if all(row.get(key) == value for key, value in query["filters"].items())
        ]
