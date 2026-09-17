"""THINK ORGANISM — Persistent Host.

The Host is a persistent Think Box with stable identity,
capability registry, and SQLite-backed memory.
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from thinkbox.workspace import ThinkBox, WorkspaceStore
from thinkbox.organism import CellResult, ThinkJobResult, CellRegistration
from thinkbox.organism.cells import Cell, CELL_REGISTRY


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class MemoryEntry:
    key: str = ""
    data: dict[str, Any] = field(default_factory=dict)
    trial: int = 0
    timestamp: str = ""


class Host:
    """Persistent Think Box Host with cells and memory."""

    box_id: str
    session_id: str
    cells: dict[str, Cell]
    db_path: str
    _memory: list[MemoryEntry]
    _ledger: list[dict[str, Any]]

    def __init__(self, box_id: str | None = None, db_path: str = ":memory:") -> None:
        self.box_id = box_id or f"box_{uuid.uuid4().hex[:12]}"
        self.session_id = f"session_{uuid.uuid4().hex[:12]}"
        self.cells = {}
        self.db_path = db_path
        self._memory: list[MemoryEntry] = []
        self._ledger: list[dict[str, Any]] = []
        if db_path != ":memory:" and not db_path.startswith(":"):
            self._init_db()

    def _init_db(self) -> None:
        path = Path(self.db_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        conn.execute(
            """CREATE TABLE IF NOT EXISTS host_state (
                box_id TEXT PRIMARY KEY,
                session_id TEXT,
                state TEXT,
                updated_at TEXT
            )""",
        )
        conn.execute(
            """CREATE TABLE IF NOT EXISTS memory (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                box_id TEXT,
                key TEXT,
                data TEXT,
                trial INTEGER,
                timestamp TEXT
            )""",
        )
        conn.commit()
        conn.close()

    def register_cell(self, cell: Cell) -> None:
        self.cells[cell.cell_id] = cell

    def discover_capabilities(self) -> list[str]:
        return [c.capability for c in self.cells.values()]

    def store_memory(self, key: str, data: dict[str, Any], trial: int = 0) -> None:
        entry = MemoryEntry(key=key, data=data, trial=trial, timestamp=_now())
        self._memory.append(entry)
        if self.db_path != ":memory:":
            conn = sqlite3.connect(self.db_path)
            conn.execute(
                "INSERT INTO memory (box_id, key, data, trial, timestamp) VALUES (?, ?, ?, ?, ?)",
                (self.box_id, key, json.dumps(data), trial, entry.timestamp),
            )
            conn.commit()
            conn.close()

    def get_memory(self, key: str) -> dict[str, Any] | None:
        for entry in reversed(self._memory):
            if entry.key == key:
                return entry.data
        if self.db_path != ":memory:":
            conn = sqlite3.connect(self.db_path)
            row = conn.execute(
                "SELECT data FROM memory WHERE box_id=? AND key=? ORDER BY id DESC LIMIT 1",
                (self.box_id, key),
            ).fetchone()
            conn.close()
            if row:
                return json.loads(row[0])
        return None

    def list_memory(self) -> list[str]:
        keys = set()
        for entry in self._memory:
            keys.add(entry.key)
        if self.db_path != ":memory:":
            conn = sqlite3.connect(self.db_path)
            rows = conn.execute(
                "SELECT DISTINCT key FROM memory WHERE box_id=?", (self.box_id,)
            ).fetchall()
            conn.close()
            for row in rows:
                keys.add(row[0])
        return list(keys)

    def run_think_job(
        self,
        intent: str,
        trial: int = 0,
        context: dict[str, Any] | None = None,
    ) -> ThinkJobResult:
        context = context or {}
        start = datetime.now(timezone.utc)
        cell_results: list[CellResult] = []
        ledger_entries: list[dict[str, Any]] = []

        memory = {}
        for key in self.list_memory():
            data = self.get_memory(key)
            if data:
                memory[key] = data

        context_with_memory = {**context, "memory": memory, "box_id": self.box_id}

        for cell_id, cell in self.cells.items():
            c_result = cell.execute(
                job_id=self.box_id,
                input_text=intent,
                context=context_with_memory,
            )
            cell_results.append(c_result)
            ledger_entries.append({
                "cell_id": cell_id,
                "cell_type": cell.cell_type,
                "job_id": self.box_id,
                "trial": trial,
                "success": c_result.success,
                "timestamp": c_result.timestamp,
            })

        verifier_context = {**context_with_memory, "cell_results": cell_results}
        verifier = self.cells.get(
            next((cid for cid, c in self.cells.items() if c.cell_type == "VERIFIER"), None)
        )
        verification = ""
        verification_success = False
        if verifier:
            v_result = verifier.execute(job_id=self.box_id, input_text="verify", context=verifier_context)
            verification = v_result.output
            verification_success = v_result.success
        else:
            verification = "no verifier registered"
            verification_success = all(r.success for r in cell_results)

        learner = self.cells.get(
            next((cid for cid, c in self.cells.items() if c.cell_type == "LEARNER"), None)
        )
        learning = ""
        if learner:
            learner_context = {**context_with_memory, "outcome": verification, "proof": "proof-data"}
            l_result = learner.execute(job_id=self.box_id, input_text="learn", context=learner_context)
            learning = l_result.output

        all_success = all(r.success for r in cell_results) and verification_success
        elapsed = (datetime.now(timezone.utc) - start).total_seconds() * 1000

        result = ThinkJobResult(
            job_id=self.box_id,
            intent=intent,
            trial=trial,
            cell_results=cell_results,
            proof=f"job-proof:{self.box_id}:trial:{trial}",
            outcome=f"Think Job trial {trial}: {len(cell_results)} cells, verification={'PASS' if verification_success else 'FAIL'}",
            success=all_success,
            execution_time_ms=round(elapsed, 3),
            memory_used=bool(memory),
            learning_applied=bool(learner),
            substrate="local",
            timestamp=_now(),
            ledger_entries=ledger_entries,
        )

        self._ledger.extend(ledger_entries)
        return result

    def persist(self) -> None:
        if self.db_path == ":memory:":
            return
        conn = sqlite3.connect(self.db_path)
        conn.execute(
            "INSERT OR REPLACE INTO host_state (box_id, session_id, state, updated_at) VALUES (?, ?, ?, ?)",
            (self.box_id, self.session_id, json.dumps({"cells": list(self.cells.keys())}), _now()),
        )
        conn.commit()
        conn.close()

    def load(self) -> None:
        if self.db_path == ":memory:":
            return
        conn = sqlite3.connect(self.db_path)
        row = conn.execute("SELECT state FROM host_state WHERE box_id=?", (self.box_id,)).fetchone()
        state = json.loads(row[0]) if row else {"cells": []}
        for cid in state.get("cells", []):
            if cid not in self.cells:
                self.register_cell(Cell(cell_id=cid, cell_type="UNKNOWN", capability=""))
        if row:
            rows = conn.execute("SELECT key, data, trial FROM memory WHERE box_id=?", (self.box_id,)).fetchall()
            for key, data, trial in rows:
                self._memory.append(MemoryEntry(key=key, data=json.loads(data), trial=trial, timestamp=_now()))
        conn.close()
