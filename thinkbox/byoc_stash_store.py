"""THINK stash SQLite local store for index + offline access."""

from __future__ import annotations

import json
import logging
import sqlite3
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class StashRecord:
    stash_id: str
    session_id: str = ""
    burst_id: str = ""
    reasoning_sha256: str = ""
    vector_id: str = ""
    proof_receipt_id: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = ""
    evidence_label: str = "simulated"


class ThinkStashStore:
    """Local SQLite store for THINK stash records.

    Provides an index for offline lookup before/after Upstash Vector ops.
    """

    def __init__(self, db_path: str | None = None) -> None:
        self._path = db_path or ":memory:"
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(self._path, check_same_thread=False)
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS think_stash (
                stash_id TEXT PRIMARY KEY,
                session_id TEXT,
                burst_id TEXT,
                reasoning_sha256 TEXT,
                vector_id TEXT,
                proof_receipt_id TEXT,
                metadata TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL,
                evidence_label TEXT NOT NULL DEFAULT 'simulated'
            )
            """
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_stash_session ON think_stash(session_id)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_stash_proof ON think_stash(proof_receipt_id)"
        )
        self._conn.commit()

    def upsert(self, record: StashRecord) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT OR REPLACE INTO think_stash (stash_id, session_id, burst_id, reasoning_sha256, vector_id, proof_receipt_id, metadata, created_at, evidence_label) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    record.stash_id,
                    record.session_id,
                    record.burst_id,
                    record.reasoning_sha256,
                    record.vector_id,
                    record.proof_receipt_id,
                    json.dumps(record.metadata, sort_keys=True),
                    record.created_at,
                    record.evidence_label,
                ),
            )
            self._conn.commit()
            logger.info("Stashed record %s", record.stash_id)

    def get(self, stash_id: str) -> dict[str, Any] | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT stash_id, session_id, burst_id, reasoning_sha256, vector_id, proof_receipt_id, metadata, created_at, evidence_label FROM think_stash WHERE stash_id = ?",
                (stash_id,),
            ).fetchone()
        if row is None:
            return None
        return {
            "stash_id": row[0],
            "session_id": row[1],
            "burst_id": row[2],
            "reasoning_sha256": row[3],
            "vector_id": row[4],
            "proof_receipt_id": row[5],
            "metadata": json.loads(row[6]),
            "created_at": row[7],
            "evidence_label": row[8],
        }

    def find_by_session(self, session_id: str) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT stash_id, session_id, burst_id, reasoning_sha256, vector_id, proof_receipt_id, metadata, created_at, evidence_label FROM think_stash WHERE session_id = ? ORDER BY created_at DESC",
                (session_id,),
            ).fetchall()
        return [self._row_to_dict(r) for r in rows]

    def find_by_proof(self, proof_receipt_id: str) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT stash_id, session_id, burst_id, reasoning_sha256, vector_id, proof_receipt_id, metadata, created_at, evidence_label FROM think_stash WHERE proof_receipt_id = ?",
                (proof_receipt_id,),
            ).fetchall()
        return [self._row_to_dict(r) for r in rows]

    def count(self) -> int:
        with self._lock:
            return self._conn.execute("SELECT COUNT(*) FROM think_stash").fetchone()[0]

    def last_harvest(self) -> dict[str, Any] | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT stash_id, session_id, burst_id, reasoning_sha256, vector_id, proof_receipt_id, metadata, created_at, evidence_label FROM think_stash ORDER BY created_at DESC LIMIT 1"
            ).fetchone()
        if row is None:
            return None
        return self._row_to_dict(row)

    def _row_to_dict(self, row: tuple) -> dict[str, Any]:
        return {
            "stash_id": row[0],
            "session_id": row[1],
            "burst_id": row[2],
            "reasoning_sha256": row[3],
            "vector_id": row[4],
            "proof_receipt_id": row[5],
            "metadata": json.loads(row[6]),
            "created_at": row[7],
            "evidence_label": row[8],
        }