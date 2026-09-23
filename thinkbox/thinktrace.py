"""KUDBEE Control Fabric — Think-trace capture and grounding scoring.

The THINK protocol captures traces (reasoning channels where available) and
scores grounded vs ungrounded reasoning. Grounded traces are backed by
fact-cards and verified state; ungrounded twins are flagged for the
disruptor pass in the evaluation agenda.

When db_path is provided, traces persist to SQLite and survive
process/session boundaries. Without db_path, traces are in-memory
only (backward compatible).
"""

from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass
class ThinkTrace:
    trace_id: str
    agent_id: str
    thought: str
    grounded: bool
    evidence_refs: list[str]
    confidence: float
    captured_at: str
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


class ThinkTraceCapture:
    """Captures and scores thinking traces for groundedness evaluation.

    Persistence: when db_path is provided, traces are also written
    to SQLite. In-memory mode (default) preserves the original behavior.
    """

    def __init__(self, max_traces: int = 10000, db_path: str | Path | None = None) -> None:
        self._traces: list[ThinkTrace] = []
        self._max = max_traces
        self._lock = threading.Lock()
        self._db_path = str(db_path) if db_path else None
        self._conn = None
        if self._db_path:
            self._init_db()

    def _init_db(self) -> None:
        Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS think_traces (
                trace_id TEXT PRIMARY KEY,
                agent_id TEXT NOT NULL,
                thought TEXT NOT NULL,
                grounded INTEGER NOT NULL,
                evidence_refs TEXT NOT NULL,
                confidence REAL NOT NULL,
                captured_at TEXT NOT NULL,
                tags TEXT NOT NULL,
                metadata TEXT NOT NULL
            )
            """
        )
        self._conn.commit()
        self._load_from_db()

    def _load_from_db(self) -> None:
        if not self._conn:
            return
        rows = self._conn.execute(
            "SELECT trace_id, agent_id, thought, grounded, evidence_refs, confidence, captured_at, tags, metadata FROM think_traces"
        ).fetchall()
        for row in rows:
            trace = ThinkTrace(
                trace_id=row[0],
                agent_id=row[1],
                thought=row[2],
                grounded=bool(row[3]),
                evidence_refs=json.loads(row[4]),
                confidence=row[5],
                captured_at=row[6],
                tags=json.loads(row[7]),
                metadata=json.loads(row[8]),
            )
            self._traces.append(trace)

    def _save_to_db(self, trace: ThinkTrace) -> None:
        if not self._conn:
            return
        self._conn.execute(
            "INSERT OR IGNORE INTO think_traces (trace_id, agent_id, thought, grounded, evidence_refs, confidence, captured_at, tags, metadata) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                trace.trace_id,
                trace.agent_id,
                trace.thought,
                1 if trace.grounded else 0,
                json.dumps(trace.evidence_refs),
                trace.confidence,
                trace.captured_at,
                json.dumps(trace.tags),
                json.dumps(trace.metadata),
            ),
        )
        self._conn.commit()

    def capture(
        self,
        agent_id: str,
        thought: str,
        evidence_refs: list[str] | None = None,
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ThinkTrace:
        grounded = bool(evidence_refs)
        trace = ThinkTrace(
            trace_id=f"trace_{uuid.uuid4().hex[:12]}",
            agent_id=agent_id,
            thought=thought,
            grounded=grounded,
            evidence_refs=evidence_refs or [],
            confidence=1.0 if grounded else 0.0,
            captured_at=datetime.now(timezone.utc).isoformat(),
            tags=tags or [],
            metadata=metadata or {},
        )
        with self._lock:
            self._traces.append(trace)
            self._save_to_db(trace)
            if len(self._traces) > self._max:
                self._traces.pop(0)
        return trace

    def find_by_id(self, trace_id: str) -> ThinkTrace | None:
        with self._lock:
            for t in self._traces:
                if t.trace_id == trace_id:
                    return t
            if self._conn:
                row = self._conn.execute(
                    "SELECT trace_id, agent_id, thought, grounded, evidence_refs, confidence, captured_at, tags, metadata FROM think_traces WHERE trace_id=?",
                    (trace_id,),
                ).fetchone()
                if row:
                    return ThinkTrace(
                        trace_id=row[0],
                        agent_id=row[1],
                        thought=row[2],
                        grounded=bool(row[3]),
                        evidence_refs=json.loads(row[4]),
                        confidence=row[5],
                        captured_at=row[6],
                        tags=json.loads(row[7]),
                        metadata=json.loads(row[8]),
                    )
            return None

    def pairs(self, limit: int = 100) -> list[tuple[ThinkTrace, ThinkTrace]]:
        with self._lock:
            grounded = [t for t in self._traces if t.grounded]
            ungrounded = [t for t in self._traces if not t.grounded]
        pairs: list[tuple[ThinkTrace, ThinkTrace]] = []
        for g in grounded[:limit]:
            best_twin = max(
                (u for u in ungrounded if u.agent_id == g.agent_id),
                key=lambda u: self._similarity(u.thought, g.thought),
                default=None,
            )
            if best_twin is not None:
                pairs.append((g, best_twin))
        return pairs

    def count(self, grounded: bool | None = None) -> int:
        with self._lock:
            if grounded is None:
                return len(self._traces)
            return len([t for t in self._traces if t.grounded == grounded])

    @staticmethod
    def _similarity(a: str, b: str) -> float:
        a_terms = set(a.lower().split())
        b_terms = set(b.lower().split())
        if not a_terms or not b_terms:
            return 0.0
        return len(a_terms & b_terms) / max(len(a_terms), len(b_terms))