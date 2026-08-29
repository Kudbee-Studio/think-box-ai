"""SQLite-backed memory store for THINK BOX AI."""

from __future__ import annotations

import json
import math
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

ETA = 0.25
CHALLENGER_S = 1.0
TOKEN_FLOOR = 0.0
TOKEN_CAP = 100.0

CHALLENGE_WEIGHTS = {
    "exec": 3.0,
    "jury": 2.0,
    "human": 2.0,
    "replay": 1.0,
}

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
CREATE TABLE IF NOT EXISTS think_tokens (
    id TEXT PRIMARY KEY,
    box_id TEXT NOT NULL,
    claim TEXT NOT NULL,
    s REAL NOT NULL DEFAULT 1.0,
    author TEXT NOT NULL DEFAULT '',
    grounded INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS challenges (
    id TEXT PRIMARY KEY,
    token_id TEXT NOT NULL,
    type TEXT NOT NULL,
    opponent REAL NOT NULL DEFAULT 1.0,
    o INTEGER NOT NULL DEFAULT 0,
    w REAL NOT NULL DEFAULT 0.0,
    created_at TEXT NOT NULL,
    FOREIGN KEY (token_id) REFERENCES think_tokens(id)
);
CREATE TABLE IF NOT EXISTS schema_migrations (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_memory_layer ON memory_entries(layer);
CREATE INDEX IF NOT EXISTS idx_memory_task ON memory_entries(task_id);
CREATE INDEX IF NOT EXISTS idx_memory_agent ON memory_entries(agent_id);
CREATE INDEX IF NOT EXISTS idx_tokens_box ON think_tokens(box_id);
CREATE INDEX IF NOT EXISTS idx_challenges_token ON challenges(token_id);
"""


def _sigmoid(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-x))


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
            except Exception as e:
                logger.debug("Failed to close SQLite connection", extra={"error": str(e)})
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

    # ------------------------------------------------------------------
    # Think tokens
    # ------------------------------------------------------------------
    def mint_token(
        self,
        box_id: str,
        claim: str,
        author: str = "",
        grounded: bool = True,
    ) -> str | None:
        """Mint a think token for a box. Returns token ID or None if duplicate."""
        if not box_id or not isinstance(box_id, str):
            raise ValueError("box_id must be a non-empty string")
        if not claim or not isinstance(claim, str):
            raise ValueError("claim must be a non-empty string")
        claim = claim[:200]
        conn = self._get_conn()
        existing = conn.execute(
            "SELECT id FROM think_tokens WHERE box_id = ? AND claim = ?",
            (box_id, claim),
        ).fetchone()
        if existing is not None:
            return None
        token_id = f"tt-{__import__('uuid').uuid4().hex[:12]}"
        conn.execute(
            "INSERT INTO think_tokens (id, box_id, claim, s, author, grounded, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (token_id, box_id, claim, 1.0, author[:50], 1 if grounded else 0, datetime.now(timezone.utc).isoformat()),
        )
        conn.commit()
        return token_id

    def get_token(self, token_id: str) -> dict | None:
        """Get a token by ID."""
        if not token_id:
            return None
        conn = self._get_conn()
        row = conn.execute("SELECT * FROM think_tokens WHERE id = ?", (token_id,)).fetchone()
        if row is None:
            return None
        return dict(row)

    def list_tokens(self, box_id: str) -> list[dict]:
        """List all tokens for a box."""
        if not box_id:
            return []
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT * FROM think_tokens WHERE box_id = ? ORDER BY created_at", (box_id,)
        ).fetchall()
        return [dict(r) for r in rows]

    def add_challenge(
        self,
        token_id: str,
        challenge_type: str,
        outcome: int,
    ) -> str | None:
        """Add a challenge to a token and update its Elo score."""
        if challenge_type not in CHALLENGE_WEIGHTS:
            return None
        if outcome not in (-1, 0, 1):
            raise ValueError("outcome must be -1, 0, or 1")
        w = CHALLENGE_WEIGHTS[challenge_type]
        conn = self._get_conn()
        token = conn.execute("SELECT s FROM think_tokens WHERE id = ?", (token_id,)).fetchone()
        if token is None:
            return None
        s_current = token["s"]
        expected = _sigmoid(s_current - CHALLENGER_S)
        s_new = s_current + ETA * w * (outcome - expected)
        s_new = max(TOKEN_FLOOR, min(TOKEN_CAP, s_new))
        challenge_id = f"ch-{__import__('uuid').uuid4().hex[:12]}"
        conn.execute(
            "INSERT INTO challenges (id, token_id, type, opponent, o, w, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (challenge_id, token_id, challenge_type, CHALLENGER_S, outcome, w, datetime.now(timezone.utc).isoformat()),
        )
        conn.execute("UPDATE think_tokens SET s = ? WHERE id = ?", (s_new, token_id))
        conn.commit()
        return challenge_id

    def list_challenges(self, token_id: str) -> list[dict]:
        """List all challenges for a token."""
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT * FROM challenges WHERE token_id = ? ORDER BY created_at", (token_id,)
        ).fetchall()
        return [dict(r) for r in rows]

    def challenge_jury(self, token_id: str, base_url: str | None) -> str | None:
        """Run a jury challenge against an LLM endpoint.

        Returns challenge_id on success, None if URL unset or fail-closed.
        """
        if not base_url:
            return None
        token = self.get_token(token_id)
        if token is None:
            return None

        import urllib.request
        import urllib.error

        prompt = (
            f"Does the following claim survive scrutiny? "
            f"Reply ONLY YES or NO.\n\nClaim: {token['claim']}"
        )
        body = json.dumps({
            "model": "local",
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 5,
        }).encode()

        req = urllib.request.Request(
            f"{base_url.rstrip('/')}/v1/chat/completions",
            data=body,
            headers={
                "Content-Type": "application/json",
                "Authorization": "Bearer local",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                data = json.loads(resp.read())
                text = data["choices"][0]["message"]["content"].strip().upper()
        except Exception:
            return None

        if "YES" in text:
            outcome = 1
        elif "NO" in text:
            outcome = -1
        else:
            outcome = 0

        return self.add_challenge(token_id, "jury", outcome)

    def challenge_replay(self, token_id: str) -> str | None:
        """Replay the most recent non-replay challenge for a token.

        Returns challenge_id on success, None if no prior challenge exists.
        """
        conn = self._get_conn()
        row = conn.execute(
            "SELECT type, o FROM challenges WHERE token_id = ? AND type != 'replay' ORDER BY created_at DESC LIMIT 1",
            (token_id,),
        ).fetchone()
        if row is None:
            return None
        return self.add_challenge(token_id, "replay", row["o"])

    def export_box(self, box_id: str) -> dict[str, Any]:
        """Export all data for a Think Box as a serializable dict."""
        if not box_id:
            raise ValueError("box_id required")
        tokens = self.list_tokens(box_id)
        for token in tokens:
            token["challenges"] = self.list_challenges(token["id"])
        return {
            "version": 1,
            "box_id": box_id,
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "tokens": tokens,
        }

    def import_box(self, data: dict[str, Any]) -> str:
        """Import a Think Box from exported data. Returns box_id."""
        if not isinstance(data, dict):
            raise ValueError("data must be a dict")
        box_id = data.get("box_id")
        if not box_id:
            raise ValueError("data.box_id required")
        for token in data.get("tokens", []):
            claim = token.get("claim", "")
            author = token.get("author", "")
            grounded = token.get("grounded", True)
            existing = self.mint_token(box_id, claim, author, grounded)
            if existing is not None:
                for ch in token.get("challenges", []):
                    self.add_challenge(existing, ch["type"], ch["o"])
        return box_id

    def delete_box(self, box_id: str) -> bool:
        """Delete a Think Box and all its tokens/challenges."""
        if not box_id:
            return False
        conn = self._get_conn()
        token_rows = conn.execute(
            "SELECT id FROM think_tokens WHERE box_id = ?", (box_id,)
        ).fetchall()
        for row in token_rows:
            conn.execute("DELETE FROM challenges WHERE token_id = ?", (row["id"],))
        conn.execute("DELETE FROM think_tokens WHERE box_id = ?", (box_id,))
        conn.commit()
        return True
