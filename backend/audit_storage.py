"""Persistent audit log storage using SQLite with session tracking."""

from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DB_PATH = Path("data/audit.db")
DB_LOCK = threading.Lock()


def _get_db() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            session_id TEXT DEFAULT '',
            action TEXT NOT NULL,
            actor TEXT NOT NULL,
            outcome TEXT NOT NULL,
            metadata TEXT DEFAULT '{}'
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON audit_log(timestamp)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_session ON audit_log(session_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_action ON audit_log(action)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_actor ON audit_log(actor)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_outcome ON audit_log(outcome)")
    conn.commit()
    return conn


def record_audit(
    action: str,
    actor: str,
    outcome: str,
    metadata: dict[str, Any] | None = None,
    session_id: str = "",
) -> None:
    with DB_LOCK:
        conn = _get_db()
        conn.execute(
            "INSERT INTO audit_log (timestamp, session_id, action, actor, outcome, metadata) VALUES (?, ?, ?, ?, ?, ?)",
            (
                datetime.now(timezone.utc).isoformat(),
                session_id,
                action,
                actor,
                outcome,
                json.dumps(metadata or {}),
            ),
        )
        conn.commit()
        conn.close()


def list_audits(
    limit: int = 100,
    action_filter: str | None = None,
    session_id: str | None = None,
) -> list[dict[str, Any]]:
    with DB_LOCK:
        conn = _get_db()
        query = "SELECT timestamp, session_id, action, actor, outcome, metadata FROM audit_log WHERE 1=1"
        params: list[Any] = []

        if action_filter:
            query += " AND action LIKE ?"
            params.append(f"%{action_filter}%")

        if session_id:
            query += " AND session_id = ?"
            params.append(session_id)

        query += " ORDER BY id DESC LIMIT ?"
        params.append(limit)

        rows = conn.execute(query, params).fetchall()
        conn.close()

    return [
        {
            "timestamp": r[0],
            "session_id": r[1],
            "action": r[2],
            "actor": r[3],
            "outcome": r[4],
            "metadata": json.loads(r[5]),
        }
        for r in rows
    ]


def count_audits(session_id: str | None = None) -> int:
    with DB_LOCK:
        conn = _get_db()
        if session_id:
            row = conn.execute("SELECT COUNT(*) FROM audit_log WHERE session_id=?", (session_id,)).fetchone()
        else:
            row = conn.execute("SELECT COUNT(*) FROM audit_log").fetchone()
        conn.close()
        return row[0] if row else 0


def list_sessions(limit: int = 50) -> list[dict[str, Any]]:
    with DB_LOCK:
        conn = _get_db()
        rows = conn.execute(
            "SELECT session_id, COUNT(*) as count, MIN(timestamp) as started, MAX(timestamp) as last_active "
            "FROM audit_log WHERE session_id != '' GROUP BY session_id ORDER BY last_active DESC LIMIT ?",
            (limit,),
        ).fetchall()
        conn.close()

    return [
        {
            "session_id": r[0],
            "audit_count": r[1],
            "started": r[2],
            "last_active": r[3],
        }
        for r in rows
    ]
