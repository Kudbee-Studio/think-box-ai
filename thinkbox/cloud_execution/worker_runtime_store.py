"""Persist worker runtime snapshots in SQLite (PR #199)."""

from __future__ import annotations

import json
import sqlite3
import threading
from pathlib import Path
from typing import Any

from thinkbox.cloud_execution.worker_lifecycle import WorkerState

_WORKER_SCHEMA = """
CREATE TABLE IF NOT EXISTS cloud_execution_workers (
    worker_id TEXT PRIMARY KEY,
    state TEXT NOT NULL,
    snapshot_json TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""


class WorkerRuntimeStore:
    def __init__(self, db_path: str | Path) -> None:
        self._path = Path(db_path)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(str(self._path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        with self._lock:
            self._conn.executescript(_WORKER_SCHEMA)
            self._conn.commit()

    def save_snapshot(self, worker_id: str, state: WorkerState, snapshot: dict[str, Any]) -> None:
        payload = json.dumps(snapshot, sort_keys=True)
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO cloud_execution_workers (worker_id, state, snapshot_json, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(worker_id) DO UPDATE SET
                    state = excluded.state,
                    snapshot_json = excluded.snapshot_json,
                    updated_at = excluded.updated_at
                """,
                (worker_id, state.value, payload, snapshot.get("updated_at", "")),
            )
            self._conn.commit()

    def load_snapshot(self, worker_id: str) -> dict[str, Any] | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT snapshot_json FROM cloud_execution_workers WHERE worker_id = ?",
                (worker_id,),
            ).fetchone()
        if row is None:
            return None
        return json.loads(row["snapshot_json"])

    def close(self) -> None:
        with self._lock:
            self._conn.close()
