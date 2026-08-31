"""Search engine for Think Box AI local indexing."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .database import get_db, project_hash


@dataclass
class SearchResult:
    id: int
    session_id: str
    role: str
    content: str
    created_at: str
    rank: float
    snippet: str = ""


@dataclass
class MemoryResult:
    id: int
    key: str
    value: str
    source: str
    rank: float


class SearchEngine:
    def __init__(self, db_path: Path | None = None):
        self.db_path = db_path

    def _conn(self) -> sqlite3.Connection:
        return get_db(self.db_path)

    def search_messages(self, query: str, project: str | None = None, limit: int = 20, context: int = 0) -> list[SearchResult]:
        conn = self._conn()
        project_h = project_hash(project) if project else None

        if project_h:
            sql = """
                SELECT m.id, m.session_id, m.role, m.content, m.created_at,
                       snippet(messages_fts, 0, '>>>', '<<<', '...', 40) as snippet,
                       bm25(messages_fts) as rank
                FROM messages_fts
                JOIN messages m ON messages_fts.rowid = m.id
                JOIN sessions s ON m.session_id = s.id
                WHERE messages_fts MATCH ? AND s.project_hash = ?
                ORDER BY rank LIMIT ?
            """
            rows = conn.execute(sql, [query, project_h, limit]).fetchall()
        else:
            sql = """
                SELECT m.id, m.session_id, m.role, m.content, m.created_at,
                       snippet(messages_fts, 0, '>>>', '<<<', '...', 40) as snippet,
                       bm25(messages_fts) as rank
                FROM messages_fts
                JOIN messages m ON messages_fts.rowid = m.id
                WHERE messages_fts MATCH ? ORDER BY rank LIMIT ?
            """
            rows = conn.execute(sql, [query, limit]).fetchall()

        results = []
        for row in rows:
            results.append(SearchResult(
                id=row["id"], session_id=row["session_id"], role=row["role"],
                content=row["content"], created_at=row["created_at"],
                rank=row["rank"], snippet=row["snippet"],
            ))

        if context > 0:
            for r in results:
                r.content = self._get_context(r.id, r.session_id, context)
        return results

    def _get_context(self, msg_id: int, session_id: str, window: int) -> str:
        conn = self._conn()
        rows = conn.execute("""
            SELECT role, content FROM messages
            WHERE session_id = ? AND id BETWEEN ? AND ? ORDER BY id
        """, [session_id, msg_id - window, msg_id + window]).fetchall()
        return "\n".join(f"[{r['role']}]: {r['content'][:200]}" for r in rows)

    def search_memory(self, query: str, project: str | None = None, limit: int = 10) -> list[MemoryResult]:
        conn = self._conn()
        project_h = project_hash(project) if project else None

        if project_h:
            sql = """
                SELECT pm.id, pm.key, pm.value, pm.source, bm25(memory_fts) as rank
                FROM memory_fts
                JOIN project_memory pm ON memory_fts.rowid = pm.id
                WHERE memory_fts MATCH ? AND pm.project_hash = ? ORDER BY rank LIMIT ?
            """
            rows = conn.execute(sql, [query, project_h, limit]).fetchall()
        else:
            sql = """
                SELECT pm.id, pm.key, pm.value, pm.source, bm25(memory_fts) as rank
                FROM memory_fts
                JOIN project_memory pm ON memory_fts.rowid = pm.id
                WHERE memory_fts MATCH ? ORDER BY rank LIMIT ?
            """
            rows = conn.execute(sql, [query, limit]).fetchall()

        return [MemoryResult(id=row["id"], key=row["key"], value=row["value"], source=row["source"], rank=row["rank"]) for row in rows]

    def search_sessions(self, query: str, project: str | None = None, limit: int = 10) -> list[dict[str, Any]]:
        conn = self._conn()
        project_h = project_hash(project) if project else None

        if project_h:
            sql = """SELECT id, title, created_at, updated_at FROM sessions
                WHERE project_hash = ? AND title LIKE ? ORDER BY updated_at DESC LIMIT ?"""
            rows = conn.execute(sql, [project_h, f"%{query}%", limit]).fetchall()
        else:
            sql = """SELECT id, title, created_at, updated_at FROM sessions
                WHERE title LIKE ? ORDER BY updated_at DESC LIMIT ?"""
            rows = conn.execute(sql, [f"%{query}%", limit]).fetchall()
        return [dict(row) for row in rows]

    def read_session(self, session_id: str) -> list[dict[str, Any]]:
        conn = self._conn()
        rows = conn.execute("""
            SELECT id, role, content, tool_name, tool_args, created_at
            FROM messages WHERE session_id = ? ORDER BY id
        """, [session_id]).fetchall()
        return [dict(row) for row in rows]

    def get_project_context(self, project: str) -> dict[str, Any]:
        conn = self._conn()
        project_h = project_hash(project)
        sessions = conn.execute("SELECT id, title, updated_at FROM sessions WHERE project_hash = ? ORDER BY updated_at DESC LIMIT 5", [project_h]).fetchall()
        memory = conn.execute("SELECT key, value, source FROM project_memory WHERE project_hash = ? ORDER BY updated_at DESC LIMIT 20", [project_h]).fetchall()
        return {"project_hash": project_h, "recent_sessions": [dict(s) for s in sessions], "memory": [dict(m) for m in memory]}

    def rebuild_index(self) -> int:
        conn = self._conn()
        conn.execute("DELETE FROM messages_fts")
        conn.execute("INSERT INTO messages_fts(rowid, content) SELECT id, content FROM messages")
        conn.execute("DELETE FROM memory_fts")
        conn.execute("INSERT INTO memory_fts(rowid, key, value) SELECT id, key, value FROM project_memory")
        count = conn.execute("SELECT COUNT(*) FROM messages_fts").fetchone()[0]
        conn.commit()
        return count

    def get_stats(self) -> dict[str, Any]:
        conn = self._conn()
        return {
            "messages": conn.execute("SELECT COUNT(*) FROM messages").fetchone()[0],
            "sessions": conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0],
            "memory_entries": conn.execute("SELECT COUNT(*) FROM project_memory").fetchone()[0],
            "projects": conn.execute("SELECT COUNT(DISTINCT project_hash) FROM sessions").fetchone()[0],
        }
