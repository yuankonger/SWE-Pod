"""The Notifications database (SQLite): the outbox, the dedup log and dropped events.

With SEEDCO_DATA_DIR set the database is a file there and survives a restart; without it, it lives in memory.
"""
import os
import sqlite3
import threading

SCHEMA = """
CREATE TABLE IF NOT EXISTS emails (
  seq INTEGER PRIMARY KEY AUTOINCREMENT, dedup_key TEXT NOT NULL UNIQUE, kind TEXT NOT NULL,
  recipient TEXT NOT NULL, subject TEXT NOT NULL, body TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS emails_recipient ON emails (recipient);
CREATE TABLE IF NOT EXISTS dropped (
  seq INTEGER PRIMARY KEY AUTOINCREMENT, event_type TEXT, reason TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS settings (name TEXT PRIMARY KEY, value TEXT NOT NULL);
"""


def default_path() -> str:
    data_dir = os.environ.get("SEEDCO_DATA_DIR")
    if not data_dir:
        return ":memory:"
    os.makedirs(data_dir, exist_ok=True)
    return os.path.join(data_dir, "notifications.db")


class Store:
    def __init__(self, path: str = ":memory:"):
        self.lock = threading.RLock()
        self.db = sqlite3.connect(path, check_same_thread=False, isolation_level=None)
        self.db.row_factory = sqlite3.Row
        self.db.executescript(SCHEMA)

    def sent(self, dedup_key: str) -> bool:
        with self.lock:
            return self.db.execute("SELECT 1 FROM emails WHERE dedup_key = ?", (dedup_key,)).fetchone() is not None

    def save_email(self, dedup_key: str, email: dict):
        """Stores the email under its dedup key: the key is unique, so the same email is never stored twice."""
        with self.lock:
            self.db.execute("INSERT INTO emails (dedup_key, kind, recipient, subject, body) VALUES (?,?,?,?,?)",
                            (dedup_key, email["kind"], email["to"], email["subject"], email["body"]))

    def emails(self, recipient=None, kind=None) -> list:
        sql, args = "SELECT * FROM emails WHERE 1=1", []
        if recipient is not None:
            sql, args = sql + " AND recipient = ?", args + [recipient]
        if kind is not None:
            sql, args = sql + " AND kind = ?", args + [kind]
        with self.lock:
            rows = self.db.execute(sql + " ORDER BY seq", args).fetchall()
        return [{"kind": r["kind"], "to": r["recipient"], "subject": r["subject"], "body": r["body"]} for r in rows]

    def drop(self, event_type, reason: str) -> int:
        """Records an event we could not use. Returns how many of that type have been dropped so far."""
        with self.lock:
            self.db.execute("INSERT INTO dropped (event_type, reason) VALUES (?,?)", (event_type, reason))
            return self.db.execute("SELECT COUNT(*) FROM dropped WHERE event_type IS ?", (event_type,)).fetchone()[0]

    def dropped(self) -> list:
        with self.lock:
            return [dict(r) for r in self.db.execute("SELECT event_type, reason FROM dropped ORDER BY seq")]

    def setting(self, name: str):
        with self.lock:
            row = self.db.execute("SELECT value FROM settings WHERE name = ?", (name,)).fetchone()
        return row[0] if row else None

    def set_setting(self, name: str, value: str):
        with self.lock:
            self.db.execute("INSERT OR REPLACE INTO settings VALUES (?, ?)", (name, value))
