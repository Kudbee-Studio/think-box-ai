"""Human-in-the-loop system — approval gates, feedback, and intervention."""

from __future__ import annotations

import sqlite3
import threading
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

DB_PATH = Path("data/hitl.db")
DB_LOCK = threading.Lock()


class ApprovalStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    DENIED = "denied"
    EXPIRED = "expired"


class FeedbackType(str, Enum):
    CORRECTION = "correction"
    RATING = "rating"
    COMMENT = "comment"
    VERDICT = "verdict"


@dataclass
class ApprovalRequest:
    id: str
    tool_name: str
    tool_args: dict[str, Any]
    reason: str
    status: ApprovalStatus
    created_at: str
    resolved_at: str | None = None
    resolved_by: str | None = None


@dataclass
class FeedbackEntry:
    id: str
    run_id: str
    type: FeedbackType
    content: str
    rating: int | None = None
    created_at: str = ""


def _get_db() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS approvals (
            id TEXT PRIMARY KEY,
            tool_name TEXT NOT NULL,
            tool_args TEXT NOT NULL,
            reason TEXT,
            status TEXT DEFAULT 'pending',
            created_at TEXT NOT NULL,
            resolved_at TEXT,
            resolved_by TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS feedback (
            id TEXT PRIMARY KEY,
            run_id TEXT NOT NULL,
            type TEXT NOT NULL,
            content TEXT NOT NULL,
            rating INTEGER,
            created_at TEXT NOT NULL
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_approvals_status ON approvals(status)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_feedback_run ON feedback(run_id)")
    conn.commit()
    return conn


class ApprovalManager:
    def request_approval(self, tool_name: str, tool_args: dict[str, Any], reason: str = "") -> str:
        approval_id = f"apr_{uuid.uuid4().hex[:8]}"
        with DB_LOCK:
            conn = _get_db()
            conn.execute(
                """INSERT INTO approvals (id, tool_name, tool_args, reason, status, created_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    approval_id,
                    tool_name,
                    json.dumps(tool_args, default=str),
                    reason,
                    ApprovalStatus.PENDING.value,
                    datetime.now(timezone.utc).isoformat(),
                ),
            )
            conn.commit()
            conn.close()
        return approval_id

    def approve(self, approval_id: str, resolved_by: str = "human") -> bool:
        return self._resolve(approval_id, ApprovalStatus.APPROVED, resolved_by)

    def deny(self, approval_id: str, resolved_by: str = "human") -> bool:
        return self._resolve(approval_id, ApprovalStatus.DENIED, resolved_by)

    def _resolve(self, approval_id: str, status: ApprovalStatus, resolved_by: str) -> bool:
        with DB_LOCK:
            conn = _get_db()
            cursor = conn.execute(
                """UPDATE approvals SET status=?, resolved_at=?, resolved_by=?
                   WHERE id=? AND status='pending'""",
                (status.value, datetime.now(timezone.utc).isoformat(), resolved_by, approval_id),
            )
            conn.commit()
            conn.close()
            return cursor.rowcount > 0

    def is_approved(self, approval_id: str) -> bool:
        with DB_LOCK:
            conn = _get_db()
            row = conn.execute(
                "SELECT status FROM approvals WHERE id=?", (approval_id,)
            ).fetchone()
            conn.close()
        return row is not None and row[0] == ApprovalStatus.APPROVED.value

    def get_pending(self) -> list[dict[str, Any]]:
        with DB_LOCK:
            conn = _get_db()
            rows = conn.execute(
                "SELECT id, tool_name, tool_args, reason, created_at FROM approvals WHERE status='pending' ORDER BY created_at"
            ).fetchall()
            conn.close()
        return [
            {
                "id": r[0],
                "tool_name": r[1],
                "tool_args": json.loads(r[2]),
                "reason": r[3],
                "created_at": r[4],
            }
            for r in rows
        ]


class FeedbackManager:
    def submit_feedback(
        self,
        run_id: str,
        feedback_type: FeedbackType,
        content: str,
        rating: int | None = None,
    ) -> str:
        feedback_id = f"fb_{uuid.uuid4().hex[:8]}"
        with DB_LOCK:
            conn = _get_db()
            conn.execute(
                """INSERT INTO feedback (id, run_id, type, content, rating, created_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    feedback_id,
                    run_id,
                    feedback_type.value,
                    content,
                    rating,
                    datetime.now(timezone.utc).isoformat(),
                ),
            )
            conn.commit()
            conn.close()
        return feedback_id

    def get_feedback(self, run_id: str) -> list[dict[str, Any]]:
        with DB_LOCK:
            conn = _get_db()
            rows = conn.execute(
                "SELECT id, type, content, rating, created_at FROM feedback WHERE run_id=? ORDER BY created_at",
                (run_id,),
            ).fetchall()
            conn.close()
        return [
            {
                "id": r[0],
                "type": r[1],
                "content": r[2],
                "rating": r[3],
                "created_at": r[4],
            }
            for r in rows
        ]

    def get_average_rating(self, run_id: str) -> float | None:
        with DB_LOCK:
            conn = _get_db()
            row = conn.execute(
                "SELECT AVG(rating) FROM feedback WHERE run_id=? AND rating IS NOT NULL",
                (run_id,),
            ).fetchone()
            conn.close()
        return round(row[0], 2) if row and row[0] else None


import json
