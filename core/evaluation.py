"""Evaluation system — test agents against known goals and measure quality."""

from __future__ import annotations

import json
import sqlite3
import statistics
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

DB_PATH = Path("data/eval.db")
DB_LOCK = threading.Lock()


class EvalStatus(str, Enum):
    PASS = "pass"
    FAIL = "fail"
    ERROR = "error"
    SKIP = "skip"


@dataclass
class EvalCase:
    id: str
    name: str
    goal: str
    expected_output: str | None = None
    expected_tools: list[str] = field(default_factory=list)
    max_iterations: int = 20
    tags: list[str] = field(default_factory=list)
    created_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "goal": self.goal,
            "expected_output": self.expected_output,
            "expected_tools": self.expected_tools,
            "max_iterations": self.max_iterations,
            "tags": self.tags,
        }


@dataclass
class EvalResult:
    eval_id: str
    case_id: str
    case_name: str
    status: EvalStatus
    output: str = ""
    tools_used: list[str] = field(default_factory=list)
    iterations: int = 0
    duration_ms: float = 0.0
    cost_usd: float = 0.0
    score: float = 0.0
    error: str | None = None
    run_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "eval_id": self.eval_id,
            "case_id": self.case_id,
            "case_name": self.case_name,
            "status": self.status.value,
            "output": self.output[:500] if self.output else "",
            "tools_used": self.tools_used,
            "iterations": self.iterations,
            "duration_ms": round(self.duration_ms, 2),
            "cost_usd": round(self.cost_usd, 6),
            "score": round(self.score, 2),
            "error": self.error,
        }


def _get_db() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS eval_cases (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            goal TEXT NOT NULL,
            expected_output TEXT,
            expected_tools TEXT DEFAULT '[]',
            max_iterations INTEGER DEFAULT 20,
            tags TEXT DEFAULT '[]',
            created_at TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS eval_results (
            id TEXT PRIMARY KEY,
            case_id TEXT NOT NULL,
            status TEXT NOT NULL,
            output TEXT,
            tools_used TEXT DEFAULT '[]',
            iterations INTEGER DEFAULT 0,
            duration_ms REAL DEFAULT 0,
            cost_usd REAL DEFAULT 0,
            score REAL DEFAULT 0,
            error TEXT,
            run_at TEXT NOT NULL
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_eval_case ON eval_results(case_id)")
    conn.commit()
    return conn


class EvalSuite:
    def add_case(
        self,
        name: str,
        goal: str,
        expected_output: str | None = None,
        expected_tools: list[str] | None = None,
        tags: list[str] | None = None,
    ) -> str:
        case_id = f"eval_{uuid.uuid4().hex[:8]}"
        with DB_LOCK:
            conn = _get_db()
            conn.execute(
                """INSERT INTO eval_cases (id, name, goal, expected_output, expected_tools, tags, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    case_id,
                    name,
                    goal,
                    expected_output,
                    json.dumps(expected_tools or []),
                    json.dumps(tags or []),
                    datetime.now(timezone.utc).isoformat(),
                ),
            )
            conn.commit()
            conn.close()
        return case_id

    def list_cases(self, tag_filter: str | None = None) -> list[dict[str, Any]]:
        with DB_LOCK:
            conn = _get_db()
            if tag_filter:
                rows = conn.execute(
                    "SELECT id, name, goal, expected_tools, tags FROM eval_cases WHERE tags LIKE ?",
                    (f"%{tag_filter}%",),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT id, name, goal, expected_tools, tags FROM eval_cases"
                ).fetchall()
            conn.close()
        return [
            {
                "id": r[0],
                "name": r[1],
                "goal": r[2],
                "expected_tools": json.loads(r[3]),
                "tags": json.loads(r[4]),
            }
            for r in rows
        ]

    def record_result(self, result: EvalResult) -> None:
        with DB_LOCK:
            conn = _get_db()
            conn.execute(
                """INSERT INTO eval_results
                   (id, case_id, status, output, tools_used, iterations,
                    duration_ms, cost_usd, score, error, run_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    result.eval_id,
                    result.case_id,
                    result.status.value,
                    result.output,
                    json.dumps(result.tools_used),
                    result.iterations,
                    result.duration_ms,
                    result.cost_usd,
                    result.score,
                    result.error,
                    datetime.now(timezone.utc).isoformat(),
                ),
            )
            conn.commit()
            conn.close()

    def get_results(self, case_id: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
        with DB_LOCK:
            conn = _get_db()
            if case_id:
                rows = conn.execute(
                    "SELECT id, case_id, status, output, tools_used, iterations, duration_ms, cost_usd, score, error, run_at FROM eval_results WHERE case_id=? ORDER BY run_at DESC LIMIT ?",
                    (case_id, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT id, case_id, status, output, tools_used, iterations, duration_ms, cost_usd, score, error, run_at FROM eval_results ORDER BY run_at DESC LIMIT ?",
                    (limit,),
                ).fetchall()
            conn.close()
        return [
            {
                "id": r[0],
                "case_id": r[1],
                "status": r[2],
                "output": (r[3] or "")[:200],
                "tools_used": json.loads(r[4]),
                "iterations": r[5],
                "duration_ms": r[6],
                "cost_usd": r[7],
                "score": r[8],
                "error": r[9],
                "run_at": r[10],
            }
            for r in rows
        ]

    def get_summary(self) -> dict[str, Any]:
        with DB_LOCK:
            conn = _get_db()
            total = conn.execute("SELECT COUNT(*) FROM eval_results").fetchone()[0]
            passes = conn.execute("SELECT COUNT(*) FROM eval_results WHERE status='pass'").fetchone()[0]
            fails = conn.execute("SELECT COUNT(*) FROM eval_results WHERE status='fail'").fetchone()[0]
            errors = conn.execute("SELECT COUNT(*) FROM eval_results WHERE status='error'").fetchone()[0]
            avg_score = conn.execute("SELECT AVG(score) FROM eval_results").fetchone()[0]
            avg_duration = conn.execute("SELECT AVG(duration_ms) FROM eval_results").fetchone()[0]
            conn.close()
        return {
            "total_runs": total,
            "passes": passes,
            "fails": fails,
            "errors": errors,
            "pass_rate": round(passes / total * 100, 1) if total else 0,
            "avg_score": round(avg_score or 0, 2),
            "avg_duration_ms": round(avg_duration or 0, 2),
        }
