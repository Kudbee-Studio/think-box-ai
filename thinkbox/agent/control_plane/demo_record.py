"""DemoRunRecord: scores, budget, timestamps persisted to SQLite/store."""

from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import sqlite3

logger = logging.getLogger(__name__)


@dataclass
class DemoRunRecord:
    run_id: str
    agent_id: str
    started_at: str
    finished_at: str | None = None
    scores: dict[str, Any] = field(default_factory=dict)
    budget_spent: float = 0.0
    burst_records: int = 0
    grounded: int = 0
    ungrounded: int = 0
    chain_valid: bool = False
    evidence_label: str = "simulated"


def create_run_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS demo_runs (
            run_id TEXT PRIMARY KEY,
            agent_id TEXT NOT NULL,
            started_at TEXT NOT NULL,
            finished_at TEXT,
            scores TEXT NOT NULL,
            budget_spent REAL NOT NULL,
            burst_records INTEGER NOT NULL,
            grounded INTEGER NOT NULL,
            ungrounded INTEGER NOT NULL,
            chain_valid INTEGER NOT NULL,
            evidence_label TEXT NOT NULL
        )
        """
    )
    conn.commit()


def save_run(conn: sqlite3.Connection, record: DemoRunRecord) -> None:
    conn.execute(
        "INSERT INTO demo_runs (run_id, agent_id, started_at, finished_at, scores, budget_spent, burst_records, grounded, ungrounded, chain_valid, evidence_label) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            record.run_id,
            record.agent_id,
            record.started_at,
            record.finished_at,
            json.dumps(record.scores, sort_keys=True),
            record.budget_spent,
            record.burst_records,
            record.grounded,
            record.ungrounded,
            1 if record.chain_valid else 0,
            record.evidence_label,
        ),
    )
    conn.commit()
    logger.info("Saved demo run record: %s", record.run_id)


def load_run(conn: sqlite3.Connection, run_id: str) -> dict[str, Any] | None:
    row = conn.execute(
        "SELECT run_id, agent_id, started_at, finished_at, scores, budget_spent, burst_records, grounded, ungrounded, chain_valid, evidence_label FROM demo_runs WHERE run_id = ?",
        (run_id,),
    ).fetchone()
    if row is None:
        return None
    return {
        "run_id": row[0],
        "agent_id": row[1],
        "started_at": row[2],
        "finished_at": row[3],
        "scores": json.loads(row[4]),
        "budget_spent": row[5],
        "burst_records": row[6],
        "grounded": row[7],
        "ungrounded": row[8],
        "chain_valid": bool(row[9]),
        "evidence_label": row[10],
    }


def last_run(conn: sqlite3.Connection) -> dict[str, Any] | None:
    row = conn.execute(
        "SELECT run_id, agent_id, started_at, finished_at, scores, budget_spent, burst_records, grounded, ungrounded, chain_valid, evidence_label FROM demo_runs ORDER BY started_at DESC LIMIT 1"
    ).fetchone()
    if row is None:
        return None
    return {
        "run_id": row[0],
        "agent_id": row[1],
        "started_at": row[2],
        "finished_at": row[3],
        "scores": json.loads(row[4]),
        "budget_spent": row[5],
        "burst_records": row[6],
        "grounded": row[7],
        "ungrounded": row[8],
        "chain_valid": bool(row[9]),
        "evidence_label": row[10],
    }
