"""Project memory system for Think Box AI.

Stores durable facts, environment notes, and corrections per project.
Inspired by Kilo Memory and vstash.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .database import get_db, project_hash, init_db


class ProjectMemory:
    def __init__(self, project_path: str, db_path: Path | None = None):
        self.project_path = str(Path(project_path).resolve())
        self.project_h = project_hash(self.project_path)
        self.db_path = db_path
        init_db(db_path)

    def _conn(self):
        return get_db(self.db_path)

    def remember(self, key: str, value: str, source: str = "auto") -> None:
        """Store or update a memory."""
        conn = self._conn()
        now = datetime.now(timezone.utc).isoformat()

        existing = conn.execute(
            "SELECT id FROM project_memory WHERE project_hash = ? AND key = ?",
            [self.project_h, key]
        ).fetchone()

        if existing:
            conn.execute("""
                UPDATE project_memory SET value = ?, source = ?, updated_at = ?
                WHERE id = ?
            """, [value, source, now, existing["id"]])
        else:
            conn.execute("""
                INSERT INTO project_memory (project_hash, key, value, source, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, [self.project_h, key, value, source, now, now])
        conn.commit()

    def forget(self, key: str) -> bool:
        """Delete a memory by key."""
        conn = self._conn()
        cursor = conn.execute(
            "DELETE FROM project_memory WHERE project_hash = ? AND key = ?",
            [self.project_h, key]
        )
        conn.commit()
        return cursor.rowcount > 0

    def get(self, key: str) -> str | None:
        """Get a memory value."""
        conn = self._conn()
        row = conn.execute(
            "SELECT value FROM project_memory WHERE project_hash = ? AND key = ?",
            [self.project_h, key]
        ).fetchone()
        return row["value"] if row else None

    def list_all(self) -> list[dict[str, Any]]:
        """List all memories for this project."""
        conn = self._conn()
        rows = conn.execute("""
            SELECT key, value, source, created_at, updated_at
            FROM project_memory
            WHERE project_hash = ?
            ORDER BY updated_at DESC
        """, [self.project_h]).fetchall()
        return [dict(row) for row in rows]

    def save_correction(self, key: str, value: str) -> None:
        """Save a user correction (takes precedence over auto memory)."""
        self.remember(key, value, source="correction")

    def save_environment(self, key: str, value: str) -> None:
        """Save environment/setup note."""
        self.remember(f"env:{key}", value, source="explicit")

    def get_environment(self) -> dict[str, str]:
        """Get all environment notes."""
        conn = self._conn()
        rows = conn.execute("""
            SELECT key, value FROM project_memory
            WHERE project_hash = ? AND key LIKE 'env:%'
        """, [self.project_h]).fetchall()
        return {row["key"][4:]: row["value"] for row in rows}

    def get_corrections(self) -> dict[str, str]:
        """Get all corrections."""
        conn = self._conn()
        rows = conn.execute("""
            SELECT key, value FROM project_memory
            WHERE project_hash = ? AND source = 'correction'
        """, [self.project_h]).fetchall()
        return {row["key"]: row["value"] for row in rows}

    def purge(self) -> int:
        """Delete all memory for this project."""
        conn = self._conn()
        cursor = conn.execute(
            "DELETE FROM project_memory WHERE project_hash = ?",
            [self.project_h]
        )
        conn.commit()
        return cursor.rowcount


class SessionStore:
    def __init__(self, project_path: str, db_path: Path | None = None):
        self.project_path = str(Path(project_path).resolve())
        self.project_h = project_hash(self.project_path)
        self.db_path = db_path
        init_db(db_path)

    def _conn(self):
        return get_db(self.db_path)

    def create_session(self, session_id: str, title: str, metadata: dict | None = None) -> None:
        """Create a new session."""
        conn = self._conn()
        now = datetime.now(timezone.utc).isoformat()
        conn.execute("""
            INSERT INTO sessions (id, title, project_hash, created_at, updated_at, metadata)
            VALUES (?, ?, ?, ?, ?, ?)
        """, [session_id, title, self.project_h, now, now, json.dumps(metadata or {})])
        conn.commit()

    def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
        tool_name: str | None = None,
        tool_args: str | None = None,
    ) -> None:
        """Add a message to a session."""
        conn = self._conn()
        now = datetime.now(timezone.utc).isoformat()
        conn.execute("""
            INSERT INTO messages (session_id, role, content, tool_name, tool_args, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, [session_id, role, content, tool_name, tool_args, now])
        conn.execute(
            "UPDATE sessions SET updated_at = ? WHERE id = ?",
            [now, session_id]
        )
        conn.commit()

    def get_session(self, session_id: str) -> dict[str, Any] | None:
        """Get session metadata."""
        conn = self._conn()
        row = conn.execute(
            "SELECT * FROM sessions WHERE id = ?", [session_id]
        ).fetchone()
        return dict(row) if row else None

    def list_sessions(self, limit: int = 20) -> list[dict[str, Any]]:
        """List sessions for this project."""
        conn = self._conn()
        rows = conn.execute("""
            SELECT id, title, created_at, updated_at, metadata
            FROM sessions
            WHERE project_hash = ?
            ORDER BY updated_at DESC
            LIMIT ?
        """, [self.project_h, limit]).fetchall()
        return [dict(row) for row in rows]
