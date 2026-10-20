"""Durable records and append-only application audit events, with atomic writes."""
import hashlib
import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from .errors import APIError


def utcnow():
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


class Store:
    def __init__(self, path):
        self.path = str(path)
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        with self.connection() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS contents (
                    content_id TEXT PRIMARY KEY, creator_id TEXT NOT NULL,
                    timestamp TEXT NOT NULL, content_type TEXT NOT NULL,
                    content_hash TEXT NOT NULL, assessment TEXT NOT NULL,
                    status TEXT NOT NULL CHECK(status IN ('classified','under_review'))
                );
                CREATE TABLE IF NOT EXISTS appeals (
                    appeal_id TEXT PRIMARY KEY,
                    content_id TEXT NOT NULL UNIQUE REFERENCES contents(content_id),
                    creator_id TEXT NOT NULL, reasoning TEXT NOT NULL,
                    timestamp TEXT NOT NULL, status TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS audit_events (
                    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_type TEXT NOT NULL,
                    content_id TEXT REFERENCES contents(content_id),
                    timestamp TEXT NOT NULL, payload TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS content_creator ON contents(creator_id);
            """)

    @contextmanager
    def connection(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        try:
            with db:
                yield db
        finally:
            db.close()

    @staticmethod
    def _public(row):
        return {"content_id": row["content_id"], "creator_id": row["creator_id"],
                "timestamp": row["timestamp"], "content_type": row["content_type"],
                "content_hash": row["content_hash"], **json.loads(row["assessment"]),
                "status": row["status"], "appeal_filed": row["status"] == "under_review"}

    @staticmethod
    def _event(db, event_type, content_id, payload):
        timestamp = utcnow()
        db.execute("INSERT INTO audit_events(event_type,content_id,timestamp,payload) VALUES(?,?,?,?)",
                   (event_type, content_id, timestamp, json.dumps(payload, allow_nan=False)))

    def submit(self, creator_id, content, assessment, content_type="text"):
        content_id, timestamp = str(uuid4()), utcnow()
        digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
        with self.connection() as db:
            db.execute("INSERT INTO contents VALUES(?,?,?,?,?,?,?)",
                       (content_id, creator_id, timestamp, content_type, digest,
                        json.dumps(assessment, allow_nan=False), "classified"))
            row = db.execute("SELECT * FROM contents WHERE content_id=?", (content_id,)).fetchone()
            record = self._public(row)
            self._event(db, "submission", content_id, record)
        return record

    def get(self, content_id):
        with self.connection() as db:
            row = db.execute("SELECT * FROM contents WHERE content_id=?", (content_id,)).fetchone()
        if row is None:
            raise APIError("content_not_found", "No content exists with that ID.", 404)
        return self._public(row)

    def log(self, limit=50):
        with self.connection() as db:
            rows = db.execute("SELECT * FROM audit_events ORDER BY event_id DESC LIMIT ?", (limit,)).fetchall()
        return [{**json.loads(row["payload"]), "event_id": row["event_id"],
                 "event_type": row["event_type"], "timestamp": row["timestamp"]} for row in rows]

