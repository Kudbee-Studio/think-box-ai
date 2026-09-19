"""Append-only ActionReceipt store with hash-chain continuity (SQLite)."""

from __future__ import annotations

import hashlib
import json
import logging
import sqlite3
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class Receipt:
    receipt_id: str
    action: str
    status: str
    reason: str
    evidence_label: str
    timestamp: str
    prev_hash: str
    entry_hash: str
    metadata: dict[str, Any] = field(default_factory=dict)


class ActionReceiptStore:
    """Append-only receipt store with hash-chain continuity.

    Each receipt references the hash of the previous receipt,
    forming a tamper-evident chain persisted to SQLite.
    """

    def __init__(self, db_path: str | Path = ":memory:") -> None:
        self._path = str(db_path)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(self._path, check_same_thread=False)
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS receipts (
                receipt_id TEXT PRIMARY KEY,
                action TEXT NOT NULL,
                status TEXT NOT NULL,
                reason TEXT NOT NULL,
                evidence_label TEXT NOT NULL,
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
        action: str,
        status: str,
        reason: str,
        evidence_label: str,
        metadata: dict[str, Any] | None = None,
    ) -> Receipt:
        with self._lock:
            prev_row = self._conn.execute(
                "SELECT entry_hash FROM receipts ORDER BY rowid DESC LIMIT 1"
            ).fetchone()
            prev_hash = prev_row[0] if prev_row else "GENESIS"
            receipt_id = f"rcpt_{uuid.uuid4().hex[:12]}"
            timestamp = datetime.now(timezone.utc).isoformat()
            meta = metadata or {}
            payload = {
                "receipt_id": receipt_id,
                "action": action,
                "status": status,
                "reason": reason,
                "evidence_label": evidence_label,
                "timestamp": timestamp,
                "prev_hash": prev_hash,
                "metadata": meta,
            }
            entry_hash = self._compute_hash(payload)
            payload["entry_hash"] = entry_hash
            row = (
                payload["receipt_id"],
                payload["action"],
                payload["status"],
                payload["reason"],
                payload["evidence_label"],
                payload["timestamp"],
                payload["prev_hash"],
                payload["entry_hash"],
                json.dumps(payload["metadata"]),
            )
            self._conn.execute(
                "INSERT INTO receipts (receipt_id, action, status, reason, evidence_label, timestamp, prev_hash, entry_hash, metadata) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                row,
            )
            self._conn.commit()
            logger.info("Appended receipt %s for action %s", receipt_id, action)
            return Receipt(**payload)

    def verify(self) -> bool:
        with self._lock:
            rows = self._conn.execute(
                "SELECT receipt_id, action, status, reason, evidence_label, timestamp, prev_hash, entry_hash, metadata FROM receipts ORDER BY rowid"
            ).fetchall()
        prev = "GENESIS"
        for row in rows:
            receipt_id, action, status, reason, evidence_label, timestamp, prev_hash, entry_hash, metadata_str = row
            if prev_hash != prev:
                return False
            payload = {
                "receipt_id": receipt_id,
                "action": action,
                "status": status,
                "reason": reason,
                "evidence_label": evidence_label,
                "timestamp": timestamp,
                "prev_hash": prev_hash,
                "metadata": json.loads(metadata_str),
            }
            if self._compute_hash(payload) != entry_hash:
                return False
            prev = entry_hash
        return True

    def latest(self, n: int = 10) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT receipt_id, action, status, reason, evidence_label, timestamp, entry_hash FROM receipts ORDER BY rowid DESC LIMIT ?",
                (n,),
            ).fetchall()
        return [
            {
                "receipt_id": r[0],
                "action": r[1],
                "status": r[2],
                "reason": r[3],
                "evidence_label": r[4],
                "timestamp": r[5],
                "entry_hash": r[6],
            }
            for r in rows
        ]

    def count(self) -> int:
        with self._lock:
            return self._conn.execute("SELECT COUNT(*) FROM receipts").fetchone()[0]

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    @staticmethod
    def _compute_hash(payload: dict[str, Any]) -> str:
        body = json.dumps(payload, sort_keys=True, default=str).encode()
        return hashlib.sha256(body).hexdigest()[:32]
