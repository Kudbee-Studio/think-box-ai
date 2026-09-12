"""Observability system for Think Box AI — traces, spans, and metrics."""

from __future__ import annotations

import json
import sqlite3
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

DB_PATH = Path("data/observability.db")
DB_LOCK = threading.Lock()


class SpanType(str, Enum):
    MODEL_CALL = "model_call"
    TOOL_CALL = "tool_call"
    AGENT_STEP = "agent_step"
    SUB_AGENT = "sub_agent"
    MEMORY_OP = "memory_op"
    CUSTOM = "custom"


class SpanStatus(str, Enum):
    OK = "ok"
    ERROR = "error"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"


@dataclass
class Span:
    trace_id: str
    span_id: str
    parent_span_id: str | None
    type: SpanType
    name: str
    start_time: float
    end_time: float | None = None
    status: SpanStatus = SpanStatus.OK
    input: dict[str, Any] | None = None
    output: dict[str, Any] | None = None
    error: str | None = None
    tokens_input: int = 0
    tokens_output: int = 0
    cost_usd: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def duration_ms(self) -> float:
        end = self.end_time or time.time()
        return (end - self.start_time) * 1000

    def to_dict(self) -> dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "span_id": self.span_id,
            "parent_span_id": self.parent_span_id,
            "type": self.type.value,
            "name": self.name,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration_ms": self.duration_ms,
            "status": self.status.value,
            "input": self.input,
            "output": self.output,
            "error": self.error,
            "tokens_input": self.tokens_input,
            "tokens_output": self.tokens_output,
            "cost_usd": self.cost_usd,
            "metadata": self.metadata,
        }


def _get_db() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS traces (
            trace_id TEXT PRIMARY KEY,
            goal TEXT,
            status TEXT DEFAULT 'running',
            started_at TEXT NOT NULL,
            completed_at TEXT,
            total_tokens_input INTEGER DEFAULT 0,
            total_tokens_output INTEGER DEFAULT 0,
            total_cost_usd REAL DEFAULT 0.0,
            total_duration_ms REAL DEFAULT 0,
            metadata TEXT DEFAULT '{}'
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS spans (
            span_id TEXT PRIMARY KEY,
            trace_id TEXT NOT NULL,
            parent_span_id TEXT,
            type TEXT NOT NULL,
            name TEXT NOT NULL,
            start_time REAL NOT NULL,
            end_time REAL,
            status TEXT DEFAULT 'ok',
            input TEXT,
            output TEXT,
            error TEXT,
            tokens_input INTEGER DEFAULT 0,
            tokens_output INTEGER DEFAULT 0,
            cost_usd REAL DEFAULT 0.0,
            metadata TEXT DEFAULT '{}',
            FOREIGN KEY (trace_id) REFERENCES traces(trace_id)
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_spans_trace ON spans(trace_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_spans_type ON spans(type)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_traces_started ON traces(started_at)")
    conn.commit()
    return conn


class Trace:
    def __init__(self, goal: str, metadata: dict[str, Any] | None = None):
        self.trace_id = str(uuid.uuid4())[:16]
        self.goal = goal
        self.metadata = metadata or {}
        self.status = "running"
        self.started_at = datetime.now(timezone.utc).isoformat()
        self.completed_at: str | None = None
        self.spans: list[Span] = []
        self._active_spans: dict[str, Span] = {}
        self._lock = threading.Lock()
        self._save_trace()

    def _save_trace(self) -> None:
        with DB_LOCK:
            conn = _get_db()
            conn.execute(
                """INSERT OR REPLACE INTO traces
                   (trace_id, goal, status, started_at, completed_at, metadata)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (self.trace_id, self.goal, self.status, self.started_at,
                 self.completed_at, json.dumps(self.metadata)),
            )
            conn.commit()
            conn.close()

    def start_span(
        self,
        name: str,
        span_type: SpanType = SpanType.CUSTOM,
        parent_span_id: str | None = None,
        input_data: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Span:
        span = Span(
            trace_id=self.trace_id,
            span_id=str(uuid.uuid4())[:12],
            parent_span_id=parent_span_id,
            type=span_type,
            name=name,
            start_time=time.time(),
            input=input_data,
            metadata=metadata or {},
        )
        with self._lock:
            self.spans.append(span)
            self._active_spans[span.span_id] = span
        return span

    def end_span(
        self,
        span: Span,
        output: dict[str, Any] | None = None,
        error: str | None = None,
        status: SpanStatus = SpanStatus.OK,
        tokens_input: int = 0,
        tokens_output: int = 0,
        cost_usd: float = 0.0,
    ) -> None:
        span.end_time = time.time()
        span.output = output
        span.error = error
        span.status = status
        span.tokens_input = tokens_input
        span.tokens_output = tokens_output
        span.cost_usd = cost_usd
        with self._lock:
            self._active_spans.pop(span.span_id, None)
        self._save_span(span)

    def _save_span(self, span: Span) -> None:
        with DB_LOCK:
            conn = _get_db()
            conn.execute(
                """INSERT OR REPLACE INTO spans
                   (span_id, trace_id, parent_span_id, type, name, start_time,
                    end_time, status, input, output, error, tokens_input,
                    tokens_output, cost_usd, metadata)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    span.span_id, span.trace_id, span.parent_span_id,
                    span.type.value, span.name, span.start_time, span.end_time,
                    span.status.value,
                    json.dumps(span.input, default=str) if span.input else None,
                    json.dumps(span.output, default=str) if span.output else None,
                    span.error, span.tokens_input, span.tokens_output,
                    span.cost_usd, json.dumps(span.metadata),
                ),
            )
            conn.commit()
            conn.close()

    def finish(self, status: str = "success") -> dict[str, Any]:
        self.status = status
        self.completed_at = datetime.now(timezone.utc).isoformat()
        total_input = sum(s.tokens_input for s in self.spans)
        total_output = sum(s.tokens_output for s in self.spans)
        total_cost = sum(s.cost_usd for s in self.spans)
        total_duration = sum(s.duration_ms for s in self.spans)
        with DB_LOCK:
            conn = _get_db()
            conn.execute(
                """UPDATE traces SET status=?, completed_at=?,
                   total_tokens_input=?, total_tokens_output=?,
                   total_cost_usd=?, total_duration_ms=?
                   WHERE trace_id=?""",
                (status, self.completed_at, total_input, total_output,
                 total_cost, total_duration, self.trace_id),
            )
            conn.commit()
            conn.close()
        return self.get_summary()

    def get_summary(self) -> dict[str, Any]:
        total_input = sum(s.tokens_input for s in self.spans)
        total_output = sum(s.tokens_output for s in self.spans)
        total_cost = sum(s.cost_usd for s in self.spans)
        return {
            "trace_id": self.trace_id,
            "goal": self.goal,
            "status": self.status,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "span_count": len(self.spans),
            "total_tokens_input": total_input,
            "total_tokens_output": total_output,
            "total_cost_usd": round(total_cost, 6),
            "total_duration_ms": round(sum(s.duration_ms for s in self.spans), 2),
            "error_count": sum(1 for s in self.spans if s.status == SpanStatus.ERROR),
        }

    def get_spans(self) -> list[dict[str, Any]]:
        return [s.to_dict() for s in sorted(self.spans, key=lambda x: x.start_time)]


def get_trace(trace_id: str) -> dict[str, Any] | None:
    with DB_LOCK:
        conn = _get_db()
        row = conn.execute(
            "SELECT * FROM traces WHERE trace_id = ?", (trace_id,)
        ).fetchone()
        if not row:
            conn.close()
            return None
        spans = conn.execute(
            "SELECT * FROM spans WHERE trace_id = ? ORDER BY start_time",
            (trace_id,),
        ).fetchall()
        conn.close()
    return {
        "trace_id": row[0],
        "goal": row[1],
        "status": row[2],
        "started_at": row[3],
        "completed_at": row[4],
        "total_tokens_input": row[5],
        "total_tokens_output": row[6],
        "total_cost_usd": row[7],
        "total_duration_ms": row[8],
        "spans": [
            {
                "span_id": s[0],
                "type": s[3],
                "name": s[4],
                "duration_ms": round((s[6] or time.time()) - s[5], 2) * 1000,
                "status": s[7],
                "tokens_input": s[10],
                "tokens_output": s[11],
                "cost_usd": s[12],
            }
            for s in spans
        ],
    }


def list_traces(limit: int = 50, status_filter: str | None = None) -> list[dict[str, Any]]:
    with DB_LOCK:
        conn = _get_db()
        if status_filter:
            rows = conn.execute(
                "SELECT trace_id, goal, status, started_at, total_tokens_input, total_tokens_output, total_cost_usd, total_duration_ms FROM traces WHERE status = ? ORDER BY started_at DESC LIMIT ?",
                (status_filter, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT trace_id, goal, status, started_at, total_tokens_input, total_tokens_output, total_cost_usd, total_duration_ms FROM traces ORDER BY started_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        conn.close()
    return [
        {
            "trace_id": r[0],
            "goal": r[1],
            "status": r[2],
            "started_at": r[3],
            "tokens_input": r[4],
            "tokens_output": r[5],
            "cost_usd": r[6],
            "duration_ms": r[7],
        }
        for r in rows
    ]


def get_metrics() -> dict[str, Any]:
    with DB_LOCK:
        conn = _get_db()
        total_traces = conn.execute("SELECT COUNT(*) FROM traces").fetchone()[0]
        total_spans = conn.execute("SELECT COUNT(*) FROM spans").fetchone()[0]
        total_tokens_in = conn.execute("SELECT COALESCE(SUM(total_tokens_input), 0) FROM traces").fetchone()[0]
        total_tokens_out = conn.execute("SELECT COALESCE(SUM(total_tokens_output), 0) FROM traces").fetchone()[0]
        total_cost = conn.execute("SELECT COALESCE(SUM(total_cost_usd), 0) FROM traces").fetchone()[0]
        avg_duration = conn.execute("SELECT COALESCE(AVG(total_duration_ms), 0) FROM traces WHERE completed_at IS NOT NULL").fetchone()[0]
        error_count = conn.execute("SELECT COUNT(*) FROM traces WHERE status = 'error'").fetchone()[0]
        tool_calls = conn.execute("SELECT COUNT(*) FROM spans WHERE type = 'tool_call'").fetchone()[0]
        model_calls = conn.execute("SELECT COUNT(*) FROM spans WHERE type = 'model_call'").fetchone()[0]
        conn.close()
    return {
        "total_traces": total_traces,
        "total_spans": total_spans,
        "total_tokens_input": total_tokens_in,
        "total_tokens_output": total_tokens_out,
        "total_cost_usd": round(total_cost, 6),
        "avg_duration_ms": round(avg_duration, 2),
        "error_count": error_count,
        "tool_calls": tool_calls,
        "model_calls": model_calls,
    }
