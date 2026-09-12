"""KUDBEE Control Fabric — Durable append-only action ledger.

Every side effect granted by the admission gate is recorded here. The
ledger is append-only and tamper-evident via a hash chain, and survives
process death via SQLite.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass
class LedgerEntry:
    entry_id: str
    agent_id: str
    capability: str
    action: str
    allowed: bool
    reason: str
    timestamp: str
    prev_hash: str
    entry_hash: str
    metadata: dict[str, Any] = field(default_factory=dict)


class ActionLedger:
    """Append-only ledger with hash chain, persisted to SQLite."""

    def __init__(self, db_path: str | Path = ":memory:") -> None:
        self._path = str(db_path)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(self._path, check_same_thread=False)
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS ledger (
                entry_id TEXT PRIMARY KEY,
                agent_id TEXT NOT NULL,
                capability TEXT NOT NULL,
                action TEXT NOT NULL,
                allowed INTEGER NOT NULL,
                reason TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                prev_hash TEXT NOT NULL,
                entry_hash TEXT NOT NULL,
                metadata TEXT NOT NULL
            )
            """
        )
        self._conn.commit()

    def append(
        self,
        agent_id: str,
        capability: str,
        action: str,
        allowed: bool,
        reason: str,
        metadata: dict[str, Any] | None = None,
    ) -> LedgerEntry:
        with self._lock:
            prev_row = self._conn.execute(
                "SELECT entry_hash FROM ledger ORDER BY rowid DESC LIMIT 1"
            ).fetchone()
            prev_hash = prev_row[0] if prev_row else "GENESIS"
            entry_id = f"ledger_{uuid.uuid4().hex[:12]}"
            payload = {
                "entry_id": entry_id,
                "agent_id": agent_id,
                "capability": capability,
                "action": action,
                "allowed": allowed,
                "reason": reason,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "prev_hash": prev_hash,
                "metadata": metadata or {},
            }
            entry_hash = self._compute_hash(payload)
            payload["entry_hash"] = entry_hash
            row = (
                payload["entry_id"],
                payload["agent_id"],
                payload["capability"],
                payload["action"],
                1 if payload["allowed"] else 0,
                payload["reason"],
                payload["timestamp"],
                payload["prev_hash"],
                payload["entry_hash"],
                json.dumps(payload["metadata"]),
            )
            self._conn.execute(
                "INSERT INTO ledger (entry_id, agent_id, capability, action, allowed, reason, timestamp, prev_hash, entry_hash, metadata) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                row,
            )
            self._conn.commit()
            return LedgerEntry(**{**payload, "allowed": payload["allowed"]})

    def verify(self) -> bool:
        """Replay the chain and confirm every hash links to its predecessor."""
        with self._lock:
            rows = self._conn.execute(
                "SELECT entry_id, agent_id, capability, action, allowed, reason, timestamp, prev_hash, entry_hash, metadata FROM ledger ORDER BY rowid"
            ).fetchall()
        prev = "GENESIS"
        for row in rows:
            entry_id, agent_id, capability, action, allowed, reason, timestamp, prev_hash, entry_hash, metadata = row
            if prev_hash != prev:
                return False
            payload = {
                "entry_id": entry_id,
                "agent_id": agent_id,
                "capability": capability,
                "action": action,
                "allowed": bool(allowed),
                "reason": reason,
                "timestamp": timestamp,
                "prev_hash": prev_hash,
                "metadata": json.loads(metadata),
            }
            if self._compute_hash(payload) != entry_hash:
                return False
            prev = entry_hash
        return True

    def entries(self, agent_id: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        with self._lock:
            query = "SELECT entry_id, agent_id, capability, action, allowed, reason, timestamp, entry_hash FROM ledger"
            params: tuple = ()
            if agent_id:
                query += " WHERE agent_id = ?"
                params = (agent_id,)
            query += " ORDER BY rowid DESC LIMIT ?"
            rows = self._conn.execute(query, (*params, limit)).fetchall()
        return [
            {
                "entry_id": r[0],
                "agent_id": r[1],
                "capability": r[2],
                "action": r[3],
                "allowed": bool(r[4]),
                "reason": r[5],
                "timestamp": r[6],
                "entry_hash": r[7],
            }
            for r in rows
        ]

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    @staticmethod
    def _compute_hash(payload: dict[str, Any]) -> str:
        body = json.dumps(payload, sort_keys=True, default=str).encode()
        return hashlib.sha256(body).hexdigest()[:32]