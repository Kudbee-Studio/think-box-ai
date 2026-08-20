"""SQLite-backed memory store for THINK BOX AI."""

from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core.foundation.errors import MemoryConflictError, MemoryError, MemoryKeyError
from core.foundation.logging import get_logger
from core.memory.schema import MemoryEntry, MemoryEntryType, MemoryLayer

logger = get_logger(__name__)

SCHEMA_VERSION = 1

_CREATE_TABLES_SQL = """
CREATE TABLE IF NOT EXISTS memory_entries (
    key TEXT PRIMARY KEY,
    layer TEXT NOT NULL,
    entry_type TEXT NOT NULL,
    value TEXT NOT NULL,
    agent_id TEXT DEFAULT '',
    task_id TEXT DEFAULT '',
    created_at TEXT NOT NULL,
    metadata TEXT DEFAULT '{}',
    confidence REAL DEFAULT 1.0
);
CREATE TABLE IF NOT EXISTS schema_migrations (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_memory_layer ON memory_entries(layer);
CREATE INDEX IF NOT EXISTS idx_memory_task ON memory_entries(task_id);
CREATE INDEX IF NOT EXISTS idx_memory_agent ON memory_entries(agent_id);
"""


class MemoryStore:
    """Thread-safe SQLite-backed key-value store for memory entries."""

    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)
        self._local = threading.local()
        self._lock = threading.Lock()
        self._ensure_schema()

    def _get_conn(self) -> sqlite3.Connection:
        if not hasattr(self._local, "conn") or self._local.conn is None:
            conn = sqlite3.connect(
                str(self.db_path),
                check_same_thread=False,
                isolation_level="DEFERRED",
            )
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA busy_timeout=5000")
            self._local.conn = conn
        return self._local.conn

    def _ensure_schema(self) -> None:
        with self._lock:
            conn = self._get_conn()
            conn.executescript(_CREATE_TABLES_SQL)
            cursor = conn.execute(
                "SELECT version FROM schema_migrations ORDER BY version DESC LIMIT 1"
            )
            row = cursor.fetchone()
            current_version = row["version"] if row else 0
            if current_version < SCHEMA_VERSION:
                logger.info("Applying memory schema migration")
                conn.execute(
                    "INSERT OR IGNORE INTO schema_migrations (version, applied_at) VALUES (?, ?)",
                    (SCHEMA_VERSION, datetime.now(timezone.utc).isoformat()),
                )
            conn.commit()

    def close(self) -> None:
        if hasattr(self._local, "conn") and self._local.conn is not None:
            try:
                self._local.conn.close()
            except Exception:
                pass
            self._local.conn = None

    def put(self, entry: MemoryEntry) -> None:
        """Store a memory entry."""
        conn = self._get_conn()
        try:
            conn.execute(
                "INSERT OR REPLACE INTO memory_entries (key, layer, entry_type, value, agent_id, task_id, created_at, metadata, confidence) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    entry.key,
                    entry.layer.value,
                    entry.entry_type.value,
                    json.dumps(entry.value),
                    entry.agent_id,
                    entry.task_id,
                    entry.created_at,
                    json.dumps(entry.metadata),
                    entry.confidence,
                ),
            )
            conn.commit()
        except sqlite3.IntegrityError as e:
            raise MemoryConflictError(
                message=f"Failed to write memory entry: {e}",
                context={"key": entry.key},
            ) from e
        except Exception as e:
            raise MemoryError(
                message=f"Memory store error: {e}",
                context={"key": entry.key},
            ) from e

    def get(self, key: str) -> MemoryEntry | None:
        """Retrieve a memory entry by key."""
        conn = self._get_conn()
        cursor = conn.execute("SELECT * FROM memory_entries WHERE key = ?", (key,))
        row = cursor.fetchone()
        if row is None:
            return None
        return self._row_to_entry(row)

    def delete(self, key: str) -> bool:
        """Delete a memory entry."""
        conn = self._get_conn()
        cursor = conn.execute("DELETE FROM memory_entries WHERE key = ?", (key,))
        conn.commit()
        return cursor.rowcount > 0

    def query(
        self,
        layer: MemoryLayer | None = None,
        task_id: str | None = None,
        agent_id: str | None = None,
        entry_type: MemoryEntryType | None = None,
        limit: int = 100,
    ) -> list[MemoryEntry]:
        """Query memory entries with optional filters."""
        conn = self._get_conn()
        conditions: list[str] = []
        params: list[Any] = []

        if layer is not None:
            conditions.append("layer = ?")
            params.append(layer.value)
        if task_id is not None:
            conditions.append("task_id = ?")
            params.append(task_id)
        if agent_id is not None:
            conditions.append("agent_id = ?")
            params.append(agent_id)
        if entry_type is not None:
            conditions.append("entry_type = ?")
            params.append(entry_type.value)

        where = " AND ".join(conditions) if conditions else "1=1"
        sql = f"SELECT * FROM memory_entries WHERE {where} ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        cursor = conn.execute(sql, params)
        return [self._row_to_entry(row) for row in cursor.fetchall()]

    def keys(self, layer: MemoryLayer | None = None) -> list[str]:
        """List all keys, optionally filtered by layer."""
        conn = self._get_conn()
        if layer is not None:
            cursor = conn.execute(
                "SELECT key FROM memory_entries WHERE layer = ? ORDER BY created_at",
                (layer.value,),
            )
        else:
            cursor = conn.execute("SELECT key FROM memory_entries ORDER BY created_at")
        return [row["key"] for row in cursor.fetchall()]

    def count(self, layer: MemoryLayer | None = None) -> int:
        """Count entries, optionally filtered by layer."""
        conn = self._get_conn()
        if layer is not None:
            cursor = conn.execute(
                "SELECT COUNT(*) as cnt FROM memory_entries WHERE layer = ?",
                (layer.value,),
            )
        else:
            cursor = conn.execute("SELECT COUNT(*) as cnt FROM memory_entries")
        return cursor.fetchone()["cnt"]

    def clear_layer(self, layer: MemoryLayer) -> int:
        """Delete all entries in a layer."""
        conn = self._get_conn()
        cursor = conn.execute("DELETE FROM memory_entries WHERE layer = ?", (layer.value,))
        conn.commit()
        return cursor.rowcount

    def _row_to_entry(self, row: sqlite3.Row) -> MemoryEntry:
        """Convert a database row to a MemoryEntry."""
        return MemoryEntry(
            key=row["key"],
            layer=MemoryLayer(row["layer"]),
            entry_type=MemoryEntryType(row["entry_type"]),
            value=json.loads(row["value"]),
            agent_id=row["agent_id"],
            task_id=row["task_id"],
            created_at=row["created_at"],
            metadata=json.loads(row["metadata"]),
            confidence=row["confidence"],
        )
