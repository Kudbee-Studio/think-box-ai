"""Organizational memory: append-only PR lifecycle receipts with hash-chain continuity."""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

_SENSITIVE_KEY_RE = re.compile(
    r"(token|secret|password|api[_-]?key|authorization|bearer|private[_-]?key)",
    re.IGNORECASE,
)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def redact_mapping(value: Any) -> Any:
    """Recursively redact sensitive keys for safe query/export."""
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for k, v in value.items():
            if _SENSITIVE_KEY_RE.search(k):
                out[k] = "[REDACTED]"
            else:
                out[k] = redact_mapping(v)
        return out
    if isinstance(value, list):
        return [redact_mapping(v) for v in value]
    if isinstance(value, str) and len(value) > 512:
        return value[:512] + "…"
    return value


@dataclass
class OrgMemoryReceipt:
    """One append-only lifecycle receipt in organizational memory."""

    receipt_id: str
    sequence: int
    timestamp: str
    run_id: str
    pr_number: int
    branch: str
    experiment_id: Optional[str]
    from_state: str
    to_state: str
    action: str
    result: str
    evidence_label: str
    prev_hash: str
    entry_hash: str
    evidence: dict[str, Any] = field(default_factory=dict)

    def to_public_dict(self) -> dict[str, Any]:
        return {
            "receipt_id": self.receipt_id,
            "sequence": self.sequence,
            "timestamp": self.timestamp,
            "run_id": self.run_id,
            "pr_number": self.pr_number,
            "branch": self.branch,
            "experiment_id": self.experiment_id,
            "from_state": self.from_state,
            "to_state": self.to_state,
            "action": self.action,
            "result": self.result,
            "evidence_label": self.evidence_label,
            "entry_hash": self.entry_hash,
            "evidence": redact_mapping(self.evidence),
        }


class OrgMemoryReceiptStore:
    """SQLite append-only store for PR lifecycle receipts and run checkpoints."""

    def __init__(self, db_path: str | Path = ":memory:") -> None:
        self._path = str(db_path)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(self._path, check_same_thread=False)
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS org_lifecycle_receipts (
                sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                receipt_id TEXT NOT NULL UNIQUE,
                timestamp TEXT NOT NULL,
                run_id TEXT NOT NULL,
                pr_number INTEGER NOT NULL,
                branch TEXT NOT NULL,
                experiment_id TEXT,
                from_state TEXT NOT NULL,
                to_state TEXT NOT NULL,
                action TEXT NOT NULL,
                result TEXT NOT NULL,
                evidence_label TEXT NOT NULL,
                prev_hash TEXT NOT NULL,
                entry_hash TEXT NOT NULL,
                evidence_json TEXT NOT NULL
            )
            """
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_org_rcpt_pr ON org_lifecycle_receipts(pr_number)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_org_rcpt_exp ON org_lifecycle_receipts(experiment_id)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_org_rcpt_run ON org_lifecycle_receipts(run_id)"
        )
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS org_lifecycle_checkpoints (
                run_id TEXT PRIMARY KEY,
                pr_number INTEGER NOT NULL,
                branch TEXT,
                snapshot_json TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                last_sequence INTEGER NOT NULL
            )
            """
        )
        self._conn.commit()

    def append_lifecycle(
        self,
        *,
        run_id: str,
        pr_number: int,
        branch: str,
        from_state: str,
        to_state: str,
        action: str,
        result: str,
        evidence: Optional[dict[str, Any]] = None,
        evidence_label: str = "simulated",
        experiment_id: Optional[str] = None,
    ) -> OrgMemoryReceipt:
        """Append one lifecycle transition receipt (fail-closed on hash break)."""
        meta = dict(evidence or {})
        exp_id = experiment_id or meta.get("experiment_id")
        if isinstance(exp_id, str):
            meta.setdefault("experiment_id", exp_id)

        with self._lock:
            prev_row = self._conn.execute(
                "SELECT entry_hash FROM org_lifecycle_receipts ORDER BY sequence DESC LIMIT 1"
            ).fetchone()
            prev_hash = prev_row[0] if prev_row else "GENESIS"
            receipt_id = f"org_rcpt_{uuid.uuid4().hex[:12]}"
            timestamp = _utc_now_iso()
            payload = {
                "receipt_id": receipt_id,
                "timestamp": timestamp,
                "run_id": run_id,
                "pr_number": pr_number,
                "branch": branch,
                "experiment_id": exp_id,
                "from_state": from_state,
                "to_state": to_state,
                "action": action,
                "result": result,
                "evidence_label": evidence_label,
                "prev_hash": prev_hash,
                "evidence": meta,
            }
            entry_hash = self._compute_hash(payload)
            self._conn.execute(
                """
                INSERT INTO org_lifecycle_receipts (
                    receipt_id, timestamp, run_id, pr_number, branch, experiment_id,
                    from_state, to_state, action, result, evidence_label,
                    prev_hash, entry_hash, evidence_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    receipt_id,
                    timestamp,
                    run_id,
                    pr_number,
                    branch,
                    exp_id,
                    from_state,
                    to_state,
                    action,
                    result,
                    evidence_label,
                    prev_hash,
                    entry_hash,
                    json.dumps(meta, sort_keys=True, default=str),
                ),
            )
            seq = self._conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            self._conn.commit()
            return OrgMemoryReceipt(
                receipt_id=receipt_id,
                sequence=int(seq),
                timestamp=timestamp,
                run_id=run_id,
                pr_number=pr_number,
                branch=branch,
                experiment_id=exp_id if isinstance(exp_id, str) else None,
                from_state=from_state,
                to_state=to_state,
                action=action,
                result=result,
                evidence_label=evidence_label,
                prev_hash=prev_hash,
                entry_hash=entry_hash,
                evidence=meta,
            )

    def save_checkpoint(
        self,
        run_id: str,
        pr_number: int,
        branch: str,
        snapshot: dict[str, Any],
    ) -> None:
        """Persist orchestrator snapshot for crash-resume."""
        with self._lock:
            last_seq = self._conn.execute(
                "SELECT COALESCE(MAX(sequence), 0) FROM org_lifecycle_receipts"
            ).fetchone()[0]
            self._conn.execute(
                """
                INSERT INTO org_lifecycle_checkpoints (
                    run_id, pr_number, branch, snapshot_json, updated_at, last_sequence
                ) VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(run_id) DO UPDATE SET
                    pr_number=excluded.pr_number,
                    branch=excluded.branch,
                    snapshot_json=excluded.snapshot_json,
                    updated_at=excluded.updated_at,
                    last_sequence=excluded.last_sequence
                """,
                (
                    run_id,
                    pr_number,
                    branch,
                    json.dumps(snapshot, sort_keys=True, default=str),
                    _utc_now_iso(),
                    int(last_seq),
                ),
            )
            self._conn.commit()

    def load_checkpoint(self, run_id: str) -> Optional[dict[str, Any]]:
        with self._lock:
            row = self._conn.execute(
                "SELECT snapshot_json FROM org_lifecycle_checkpoints WHERE run_id = ?",
                (run_id,),
            ).fetchone()
        if not row:
            return None
        return json.loads(row[0])

    def verify(self) -> bool:
        """Verify hash-chain and sequence continuity."""
        with self._lock:
            rows = self._conn.execute(
                """
                SELECT sequence, receipt_id, timestamp, run_id, pr_number, branch,
                       experiment_id, from_state, to_state, action, result,
                       evidence_label, prev_hash, entry_hash, evidence_json
                FROM org_lifecycle_receipts ORDER BY sequence
                """
            ).fetchall()
        prev_hash = "GENESIS"
        expected_seq = 1
        for row in rows:
            seq, receipt_id, timestamp, run_id, pr_number, branch, experiment_id, from_state, to_state, action, result, evidence_label, prev_row_hash, entry_hash, evidence_json = row
            if int(seq) != expected_seq:
                return False
            if prev_row_hash != prev_hash:
                return False
            evidence = json.loads(evidence_json)
            payload = {
                "receipt_id": receipt_id,
                "timestamp": timestamp,
                "run_id": run_id,
                "pr_number": pr_number,
                "branch": branch,
                "experiment_id": experiment_id,
                "from_state": from_state,
                "to_state": to_state,
                "action": action,
                "result": result,
                "evidence_label": evidence_label,
                "prev_hash": prev_row_hash,
                "evidence": evidence,
            }
            if self._compute_hash(payload) != entry_hash:
                return False
            prev_hash = entry_hash
            expected_seq += 1
        return True

    def query(
        self,
        *,
        pr_number: Optional[int] = None,
        experiment_id: Optional[str] = None,
        since: Optional[str] = None,
        until: Optional[str] = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Query receipts with redaction-safe public fields."""
        clauses: list[str] = []
        params: list[Any] = []
        if pr_number is not None:
            clauses.append("pr_number = ?")
            params.append(pr_number)
        if experiment_id is not None:
            clauses.append("experiment_id = ?")
            params.append(experiment_id)
        if since is not None:
            clauses.append("timestamp >= ?")
            params.append(since)
        if until is not None:
            clauses.append("timestamp <= ?")
            params.append(until)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        sql = f"""
            SELECT sequence, receipt_id, timestamp, run_id, pr_number, branch,
                   experiment_id, from_state, to_state, action, result,
                   evidence_label, entry_hash, evidence_json
            FROM org_lifecycle_receipts {where}
            ORDER BY sequence DESC LIMIT ?
        """
        params.append(limit)
        with self._lock:
            rows = self._conn.execute(sql, params).fetchall()
        out: list[dict[str, Any]] = []
        for row in rows:
            evidence = json.loads(row[13])
            rcpt = OrgMemoryReceipt(
                receipt_id=row[1],
                sequence=int(row[0]),
                timestamp=row[2],
                run_id=row[3],
                pr_number=int(row[4]),
                branch=row[5],
                experiment_id=row[6],
                from_state=row[7],
                to_state=row[8],
                action=row[9],
                result=row[10],
                evidence_label=row[11],
                prev_hash="",
                entry_hash=row[12],
                evidence=evidence,
            )
            out.append(rcpt.to_public_dict())
        return out

    def count(self) -> int:
        with self._lock:
            return int(
                self._conn.execute("SELECT COUNT(*) FROM org_lifecycle_receipts").fetchone()[0]
            )

    def distinct_pr_numbers(self) -> list[int]:
        """Distinct GitHub PR numbers present in the receipt chain."""
        with self._lock:
            rows = self._conn.execute(
                """
                SELECT DISTINCT pr_number FROM org_lifecycle_receipts
                WHERE pr_number > 0
                ORDER BY pr_number ASC
                """
            ).fetchall()
        return [int(r[0]) for r in rows]

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    @staticmethod
    def _compute_hash(payload: dict[str, Any]) -> str:
        body = json.dumps(payload, sort_keys=True, default=str).encode()
        return hashlib.sha256(body).hexdigest()[:32]
