"""The Notifications database (SQLite): the outbox, the dedup log, consumer offsets and dropped events.

With SEEDCO_DATA_DIR set the database is a file there and survives a restart; without it, it lives in memory.
"""
import os
import sqlite3
import threading

SCHEMA = """
CREATE TABLE IF NOT EXISTS emails (
  seq INTEGER PRIMARY KEY AUTOINCREMENT, event_id TEXT NOT NULL UNIQUE, kind TEXT NOT NULL,
  customer_id TEXT NOT NULL, recipient TEXT NOT NULL, subject TEXT NOT NULL, body TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS emails_customer ON emails (customer_id);
CREATE TABLE IF NOT EXISTS seen_events (event_id TEXT PRIMARY KEY, event_type TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS offsets (topic TEXT PRIMARY KEY, next_offset INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS dropped (
  seq INTEGER PRIMARY KEY AUTOINCREMENT, event_id TEXT, event_type TEXT, reason TEXT NOT NULL);
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

    def seen(self, event_id: str) -> bool:
        with self.lock:
            return self.db.execute("SELECT 1 FROM seen_events WHERE event_id = ?", (event_id,)).fetchone() is not None

    def save_email(self, event_id: str, event_type: str, email: dict):
        """Records the event as seen and its email in one transaction: one email per event, even across restarts."""
        with self.lock:
            self.db.execute("BEGIN")
            try:
                self.db.execute("INSERT INTO seen_events VALUES (?, ?)", (event_id, event_type))
                self.db.execute(
                    "INSERT INTO emails (event_id, kind, customer_id, recipient, subject, body) VALUES (?,?,?,?,?,?)",
                    (event_id, email["kind"], email["customer_id"], email["to"], email["subject"], email["body"]))
                self.db.execute("COMMIT")
            except Exception:
                self.db.execute("ROLLBACK")
                raise

    def emails(self, customer_id=None, kind=None) -> list:
        sql, args = "SELECT * FROM emails WHERE 1=1", []
        if customer_id is not None:
            sql, args = sql + " AND customer_id = ?", args + [customer_id]
        if kind is not None:
            sql, args = sql + " AND kind = ?", args + [kind]
        with self.lock:
            rows = self.db.execute(sql + " ORDER BY seq", args).fetchall()
        return [{"event_id": r["event_id"], "kind": r["kind"], "customer_id": r["customer_id"], "to": r["recipient"],
                 "subject": r["subject"], "body": r["body"]} for r in rows]

    def drop(self, event_id, event_type, reason: str) -> int:
        """Records an event we could not use. Returns how many of that type have been dropped so far."""
        with self.lock:
            self.db.execute("INSERT INTO dropped (event_id, event_type, reason) VALUES (?,?,?)",
                            (event_id, event_type, reason))
            return self.db.execute("SELECT COUNT(*) FROM dropped WHERE event_type IS ?", (event_type,)).fetchone()[0]

    def dropped(self) -> list:
        with self.lock:
            return [dict(r) for r in self.db.execute("SELECT event_id, event_type, reason FROM dropped ORDER BY seq")]

    def offset(self, topic: str) -> int:
        with self.lock:
            row = self.db.execute("SELECT next_offset FROM offsets WHERE topic = ?", (topic,)).fetchone()
        return row[0] if row else 0

    def set_offset(self, topic: str, next_offset: int):
        with self.lock:
            self.db.execute("INSERT INTO offsets VALUES (?, ?) ON CONFLICT(topic) DO UPDATE SET next_offset = ?",
                            (topic, next_offset, next_offset))
