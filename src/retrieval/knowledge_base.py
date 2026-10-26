import json
from pathlib import Path
from src.config import KB_DIR


class KnowledgeBase:
    def __init__(self, directory=KB_DIR):
        self.collections = {}
        directory = Path(directory)
        paths = sorted(directory.glob("*.json"))
        if not paths:
            raise ValueError(f"No JSON collections in {directory}")
        for path in paths:
            name = path.stem
            rows = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(rows, list) or any(not isinstance(row, dict) or not row.get("id") for row in rows):
                raise ValueError(f"{path} must contain a list of records with IDs")
            if len({row["id"] for row in rows}) != len(rows):
                raise ValueError(f"Duplicate IDs in {path}")
            self.collections[name] = rows

    def execute(self, query):
        return [
            row for row in self.collections[query["collection"]]
            if all(row.get(key) == value for key, value in query["filters"].items())
        ]
