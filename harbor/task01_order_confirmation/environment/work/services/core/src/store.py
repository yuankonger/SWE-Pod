"""The Core database (SQLite). Records are JSON documents by kind and id, with one lookup key per record.

With SEEDCO_DATA_DIR set the database is a file there and survives a restart; without it, it lives in memory.
"""
import json
import os
import sqlite3
import threading

SCHEMA = """
CREATE TABLE IF NOT EXISTS docs (
  seq INTEGER PRIMARY KEY AUTOINCREMENT, kind TEXT NOT NULL, id TEXT NOT NULL, lookup TEXT, body TEXT NOT NULL,
  UNIQUE (kind, id));
CREATE INDEX IF NOT EXISTS docs_lookup ON docs (kind, lookup);
CREATE TABLE IF NOT EXISTS counters (name TEXT PRIMARY KEY, value INTEGER NOT NULL);
"""


def default_path() -> str:
    data_dir = os.environ.get("SEEDCO_DATA_DIR")
    if not data_dir:
        return ":memory:"
    os.makedirs(data_dir, exist_ok=True)
    return os.path.join(data_dir, "core.db")


class Store:
    def __init__(self, path: str = ":memory:"):
        self.lock = threading.RLock()
        self.db = sqlite3.connect(path, check_same_thread=False, isolation_level=None)
        self.db.executescript(SCHEMA)

    def put(self, kind: str, doc: dict, lookup: str = None) -> dict:
        """Inserts the document, or replaces the one with the same id. Returns it."""
        with self.lock:
            self.db.execute(
                "INSERT INTO docs (kind, id, lookup, body) VALUES (?, ?, ?, ?) "
                "ON CONFLICT (kind, id) DO UPDATE SET lookup = excluded.lookup, body = excluded.body",
                (kind, doc["id"], lookup, json.dumps(doc)))
        return doc

    def get(self, kind: str, doc_id: str):
        with self.lock:
            row = self.db.execute("SELECT body FROM docs WHERE kind = ? AND id = ?", (kind, doc_id)).fetchone()
        return json.loads(row[0]) if row else None

    def all(self, kind: str, lookup: str = None) -> list:
        """Documents of one kind in the order they were first written, optionally with one lookup key."""
        with self.lock:
            rows = self.db.execute(
                "SELECT body FROM docs WHERE kind = ? AND (? IS NULL OR lookup = ?) ORDER BY seq",
                (kind, lookup, lookup)).fetchall()
        return [json.loads(r[0]) for r in rows]

    def delete(self, kind: str, doc_id: str):
        with self.lock:
            self.db.execute("DELETE FROM docs WHERE kind = ? AND id = ?", (kind, doc_id))

    def next(self, name: str) -> int:
        with self.lock:
            self.db.execute("INSERT INTO counters VALUES (?, 1) ON CONFLICT (name) DO UPDATE SET value = value + 1", (name,))
            return self.db.execute("SELECT value FROM counters WHERE name = ?", (name,)).fetchone()[0]
