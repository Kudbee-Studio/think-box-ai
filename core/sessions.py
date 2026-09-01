"""Session manager — persistent conversation memory and replay."""

from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DB_PATH = Path("data/sessions.db")
DB_LOCK = threading.Lock()


def _get_db() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            session_id TEXT PRIMARY KEY,
            title TEXT,
            status TEXT DEFAULT 'active',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            message_count INTEGER DEFAULT 0,
            total_tokens INTEGER DEFAULT 0,
            metadata TEXT DEFAULT '{}'
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id TEXT PRIMARY KEY,
            session_id TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            tokens INTEGER DEFAULT 0,
            tool_name TEXT,
            timestamp TEXT NOT NULL,
            FOREIGN KEY (session_id) REFERENCES sessions(session_id)
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id)")
    conn.commit()
    return conn


class SessionManager:
    def create_session(self, title: str = "", metadata: dict[str, Any] | None = None) -> str:
        session_id = f"sess_{uuid.uuid4().hex[:12]}"
        now = datetime.now(timezone.utc).isoformat()
        with DB_LOCK:
            conn = _get_db()
            conn.execute(
                """INSERT INTO sessions (session_id, title, status, created_at, updated_at, metadata)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (session_id, title or "New Session", "active", now, now, json.dumps(metadata or {})),
            )
            conn.commit()
            conn.close()
        return session_id

    def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
        tokens: int = 0,
        tool_name: str | None = None,
    ) -> str:
        msg_id = f"msg_{uuid.uuid4().hex[:10]}"
        now = datetime.now(timezone.utc).isoformat()
        with DB_LOCK:
            conn = _get_db()
            conn.execute(
                """INSERT INTO messages (id, session_id, role, content, tokens, tool_name, timestamp)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (msg_id, session_id, role, content, tokens, tool_name, now),
            )
            conn.execute(
                """UPDATE sessions SET message_count = message_count + 1,
                   total_tokens = total_tokens + ?, updated_at = ?
                   WHERE session_id = ?""",
                (tokens, now, session_id),
            )
            conn.commit()
            conn.close()
        return msg_id

    def get_session(self, session_id: str) -> dict[str, Any] | None:
        with DB_LOCK:
            conn = _get_db()
            row = conn.execute(
                "SELECT session_id, title, status, created_at, updated_at, message_count, total_tokens FROM sessions WHERE session_id=?",
                (session_id,),
            ).fetchone()
            if not row:
                conn.close()
                return None
            messages = conn.execute(
                "SELECT role, content, tokens, tool_name, timestamp FROM messages WHERE session_id=? ORDER BY timestamp",
                (session_id,),
            ).fetchall()
            conn.close()
        return {
            "session_id": row[0],
            "title": row[1],
            "status": row[2],
            "created_at": row[3],
            "updated_at": row[4],
            "message_count": row[5],
            "total_tokens": row[6],
            "messages": [
                {
                    "role": m[0],
                    "content": m[1],
                    "tokens": m[2],
                    "tool_name": m[3],
                    "timestamp": m[4],
                }
                for m in messages
            ],
        }

    def list_sessions(self, limit: int = 20, status_filter: str | None = None) -> list[dict[str, Any]]:
        with DB_LOCK:
            conn = _get_db()
            if status_filter:
                rows = conn.execute(
                    "SELECT session_id, title, status, updated_at, message_count, total_tokens FROM sessions WHERE status=? ORDER BY updated_at DESC LIMIT ?",
                    (status_filter, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT session_id, title, status, updated_at, message_count, total_tokens FROM sessions ORDER BY updated_at DESC LIMIT ?",
                    (limit,),
                ).fetchall()
            conn.close()
        return [
            {
                "session_id": r[0],
                "title": r[1],
                "status": r[2],
                "updated_at": r[3],
                "message_count": r[4],
                "total_tokens": r[5],
            }
            for r in rows
        ]

    def search_sessions(self, query: str, limit: int = 20) -> list[dict[str, Any]]:
        with DB_LOCK:
            conn = _get_db()
            rows = conn.execute(
                """SELECT DISTINCT s.session_id, s.title, s.status, s.updated_at, s.message_count
                   FROM sessions s JOIN messages m ON s.session_id = m.session_id
                   WHERE m.content LIKE ? OR s.title LIKE ?
                   ORDER BY s.updated_at DESC LIMIT ?""",
                (f"%{query}%", f"%{query}%", limit),
            ).fetchall()
            conn.close()
        return [
            {
                "session_id": r[0],
                "title": r[1],
                "status": r[2],
                "updated_at": r[3],
                "message_count": r[4],
            }
            for r in rows
        ]

    def delete_session(self, session_id: str) -> bool:
        with DB_LOCK:
            conn = _get_db()
            conn.execute("DELETE FROM messages WHERE session_id=?", (session_id,))
            cursor = conn.execute("DELETE FROM sessions WHERE session_id=?", (session_id,))
            conn.commit()
            conn.close()
            return cursor.rowcount > 0
