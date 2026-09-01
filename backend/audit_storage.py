"""Persistent audit log storage using SQLite."""

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
            action TEXT NOT NULL,
            actor TEXT NOT NULL,
            outcome TEXT NOT NULL,
            metadata TEXT DEFAULT '{}'
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON audit_log(timestamp)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_action ON audit_log(action)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_actor ON audit_log(actor)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_outcome ON audit_log(outcome)")
    conn.commit()
    return conn


def record_audit(action: str, actor: str, outcome: str, metadata: dict[str, Any] | None = None) -> None:
    with DB_LOCK:
        conn = _get_db()
        conn.execute(
            "INSERT INTO audit_log (timestamp, action, actor, outcome, metadata) VALUES (?, ?, ?, ?, ?)",
            (
                datetime.now(timezone.utc).isoformat(),
                action,
                actor,
                outcome,
                json.dumps(metadata or {}),
            ),
        )
        conn.commit()
        conn.close()


def list_audits(limit: int = 100, action_filter: str | None = None) -> list[dict[str, Any]]:
    with DB_LOCK:
        conn = _get_db()
        if action_filter:
            rows = conn.execute(
                "SELECT timestamp, action, actor, outcome, metadata FROM audit_log WHERE action LIKE ? ORDER BY id DESC LIMIT ?",
                (f"%{action_filter}%", limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT timestamp, action, actor, outcome, metadata FROM audit_log ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        conn.close()

    return [
        {
            "timestamp": r[0],
            "action": r[1],
            "actor": r[2],
            "outcome": r[3],
            "metadata": json.loads(r[4]),
        }
        for r in rows
    ]


def count_audits() -> int:
    with DB_LOCK:
        conn = _get_db()
        row = conn.execute("SELECT COUNT(*) FROM audit_log").fetchone()
        conn.close()
        return row[0] if row else 0
