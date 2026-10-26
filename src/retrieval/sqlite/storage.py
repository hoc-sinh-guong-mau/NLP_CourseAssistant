"""Build SQLite directly from raw sources through validated in-memory records."""
import json
import os
from pathlib import Path
import sqlite3
import tempfile

from src.config import RAW_DIR, SQLITE_PATH, SQLITE_TIMEOUT_SECONDS
from src.retrieval.exceptions import KnowledgeBaseError
from src.retrieval.normalization import build_collections

SCHEMA_VERSION = '1'
SCHEMA = '''
CREATE TABLE kb_metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE kb_collections (name TEXT PRIMARY KEY);
CREATE TABLE kb_records (
    collection TEXT NOT NULL REFERENCES kb_collections(name),
    entity_id TEXT NOT NULL,
    position INTEGER NOT NULL,
    document TEXT NOT NULL CHECK(json_valid(document)),
    PRIMARY KEY(collection, entity_id),
    UNIQUE(collection, position)
);
'''


def open_snapshot(path):
    path = Path(path)
    try:
        connection = sqlite3.connect(path.resolve().as_uri() + '?mode=ro', uri=True, timeout=SQLITE_TIMEOUT_SECONDS)
        connection.execute('PRAGMA query_only=ON')
        connection.execute("SELECT json_valid('{}')")
        version = connection.execute("SELECT value FROM kb_metadata WHERE key='schema_version'").fetchone()
        if version != (SCHEMA_VERSION,):
            raise KnowledgeBaseError('Unsupported SQLite KB schema', context={'path':str(path)})
        return connection
    except (sqlite3.Error, KnowledgeBaseError) as exc:
        if 'connection' in locals():
            connection.close()
        raise KnowledgeBaseError('Cannot open SQLite snapshot; run python -m src.main build-kb first', context={'path':str(path)}) from exc


def build_sqlite(raw_dir=RAW_DIR, database=SQLITE_PATH):
    return build_snapshot(build_collections(raw_dir), database)


def build_snapshot(collections, database):
    """Internal writer; callers provide validated normalized records."""
    database = Path(database)
    if database.suffix not in {'.sqlite3', '.sqlite', '.db'}:
        raise KnowledgeBaseError('SQLite destination needs .sqlite3, .sqlite or .db suffix')
    if database.exists():
        # Only replace a snapshot with our schema; never overwrite a legacy DB.
        with_connection = open_snapshot(database)
        with_connection.close()
    temporary = None
    connection = None
    try:
        database.parent.mkdir(parents=True, exist_ok=True)
        fd, temporary = tempfile.mkstemp(prefix='.kb-', suffix='.sqlite3', dir=database.parent)
        os.close(fd)
        connection = sqlite3.connect(temporary)
        connection.execute('PRAGMA foreign_keys=ON')
        connection.executescript(SCHEMA)
        with connection:
            connection.execute('INSERT INTO kb_metadata VALUES (?, ?)', ('schema_version',SCHEMA_VERSION))
            for name, records in collections.items():
                connection.execute('INSERT INTO kb_collections VALUES (?)', (name,))
                connection.executemany('INSERT INTO kb_records VALUES (?, ?, ?, ?)', [
                    (name, row['id'], position, json.dumps(row, ensure_ascii=False, allow_nan=False))
                    for position, row in enumerate(records)
                ])
        connection.close()
        connection = None
        os.replace(temporary, database)
        temporary = None
    except (OSError, sqlite3.Error, ValueError) as exc:
        raise KnowledgeBaseError('Cannot build SQLite snapshot', context={'path':str(database)}) from exc
    finally:
        if connection is not None:
            connection.close()
        if temporary is not None:
            Path(temporary).unlink(missing_ok=True)
    return {name:len(records) for name,records in collections.items()}
