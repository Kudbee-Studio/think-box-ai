"""KUDBEE Control Fabric — Think-trace capture and grounding scoring.

The THINK protocol captures traces (reasoning channels where available) and
scores grounded vs ungrounded reasoning. Grounded traces are backed by
fact-cards and verified state; ungrounded twins are flagged for the
disruptor pass in the evaluation agenda.
"""

from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
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
    """Captures and scores thinking traces for groundedness evaluation."""

    def __init__(self, max_traces: int = 10000) -> None:
        self._traces: list[ThinkTrace] = []
        self._max = max_traces
        self._lock = threading.Lock()

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
            if len(self._traces) > self._max:
                self._traces.pop(0)
        return trace

    def pairs(self, limit: int = 100) -> list[tuple[ThinkTrace, ThinkTrace]]:
        """Contrast pairs: grounded trace vs best ungrounded twin."""
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

    def list_recent(self, limit: int = 100) -> list[ThinkTrace]:
        """Return newest traces up to ``limit`` (for durable export / CLI)."""
        with self._lock:
            if limit <= 0:
                return []
            return list(self._traces[-limit:])

    @staticmethod
    def _similarity(a: str, b: str) -> float:
        a_terms = set(a.lower().split())
        b_terms = set(b.lower().split())
        if not a_terms or not b_terms:
            return 0.0
        return len(a_terms & b_terms) / max(len(a_terms), len(b_terms))