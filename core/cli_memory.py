"""Persistent memory system for Think Box AI CLI.

Stores context across CLI invocations so the agent remembers:
- Previous commands and their results
- User preferences
- Project state
- Learned facts
"""

from __future__ import annotations

import json
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DB_PATH = Path("data/cli_memory.db")


class PersistentMemory:
    """Cross-session memory for CLI."""

    def __init__(self):
        import sqlite3
        self.conn = sqlite3.connect(str(DB_PATH))
        self.conn.row_factory = sqlite3.Row
        self._init_db()

    def _init_db(self):
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS memories (
                key TEXT PRIMARY KEY,
                category TEXT NOT NULL,  -- command, preference, fact, result, context
                value TEXT NOT NULL,
                session_id TEXT DEFAULT '',
                importance REAL DEFAULT 1.0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                access_count INTEGER DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY,
                started_at TEXT NOT NULL,
                ended_at TEXT,
                command_count INTEGER DEFAULT 0,
                summary TEXT DEFAULT ''
            );
            CREATE TABLE IF NOT EXISTS commands (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT,
                command TEXT NOT NULL,
                result TEXT,
                timestamp TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_memories_category ON memories(category);
            CREATE INDEX IF NOT EXISTS idx_memories_importance ON memories(importance);
            CREATE INDEX IF NOT EXISTS idx_commands_session ON commands(session_id);
        """)
        self.conn.commit()

    def remember(self, key: str, value: Any, category: str = "fact", importance: float = 1.0):
        """Store a memory."""
        now = datetime.now(timezone.utc).isoformat()
        value_str = json.dumps(value) if not isinstance(value, str) else value
        self.conn.execute("""
            INSERT OR REPLACE INTO memories (key, category, value, importance, created_at, updated_at, access_count)
            VALUES (?, ?, ?, ?, COALESCE((SELECT created_at FROM memories WHERE key=?), ?), ?, COALESCE((SELECT access_count FROM memories WHERE key=?), 0) + 1)
        """, (key, category, value_str, importance, key, now, now, key))
        self.conn.commit()

    def recall(self, key: str) -> Any | None:
        """Retrieve a memory by key."""
        row = self.conn.execute("SELECT value FROM memories WHERE key=?", (key,)).fetchone()
        if row:
            self.conn.execute("UPDATE memories SET access_count = access_count + 1 WHERE key=?", (key,))
            self.conn.commit()
            try:
                return json.loads(row["value"])
            except json.JSONDecodeError:
                return row["value"]
        return None

    def search(self, query: str, category: str | None = None, limit: int = 10) -> list[dict]:
        """Search memories by content."""
        sql = "SELECT key, category, value, importance FROM memories WHERE value LIKE ? OR key LIKE ?"
        params = [f"%{query}%", f"%{query}%"]
        if category:
            sql += " AND category = ?"
            params.append(category)
        sql += " ORDER BY importance DESC, access_count DESC LIMIT ?"
        params.append(limit)
        rows = self.conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]

    def get_context(self, limit: int = 20) -> str:
        """Get relevant context for CLI injection."""
        rows = self.conn.execute(
            "SELECT key, value, category FROM memories ORDER BY importance DESC, access_count DESC LIMIT ?",
            (limit,)
        ).fetchall()
        context = []
        for r in rows:
            context.append(f"[{r['category']}] {r['key']}: {r['value'][:200]}")
        return "\n".join(context)

    def list_all(self, category: str | None = None) -> list[dict]:
        """List all memories."""
        sql = "SELECT key, category, value, importance, access_count FROM memories"
        params = []
        if category:
            sql += " WHERE category = ?"
            params.append(category)
        sql += " ORDER BY importance DESC"
        rows = self.conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]

    def forget(self, key: str):
        """Delete a memory."""
        self.conn.execute("DELETE FROM memories WHERE key=?", (key,))
        self.conn.commit()

    def log_command(self, session_id: str, command: str, result: str = ""):
        """Log a CLI command."""
        self.conn.execute(
            "INSERT INTO commands (session_id, command, result, timestamp) VALUES (?, ?, ?, ?)",
            (session_id, command, result[:1000], datetime.now(timezone.utc).isoformat())
        )
        self.conn.commit()

    def get_command_history(self, session_id: str | None = None, limit: int = 50) -> list[dict]:
        """Get command history."""
        if session_id:
            rows = self.conn.execute(
                "SELECT command, result, timestamp FROM commands WHERE session_id=? ORDER BY timestamp DESC LIMIT ?",
                (session_id, limit)
            ).fetchall()
        else:
            rows = self.conn.execute(
                "SELECT command, result, timestamp FROM commands ORDER BY timestamp DESC LIMIT ?",
                (limit,)
            ).fetchall()
        return [dict(r) for r in rows]


# Global instance
memory = PersistentMemory()
