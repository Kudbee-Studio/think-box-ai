"""THINK ORGANISM — Learning Extraction and Persistence.

Extracts supported learning from outcomes and persists it
for reuse across trials. Learning must be evidence-based,
not fabricated.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class LearningEntry:
    learning_id: str = ""
    trial: int = 0
    cell_type: str = ""
    outcome: str = ""
    proof: str = ""
    supported_by: str = ""
    extracted_at: str = ""
    persisted: bool = False


class LearningStore:
    """Manages learning persistence in SQLite."""

    def __init__(self, db_path: str = ":memory:") -> None:
        self.db_path = db_path
        if db_path != ":memory:" and not db_path.startswith(":"):
            self._init_db()

    def _init_db(self) -> None:
        path = Path(self.db_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        conn.execute(
            """CREATE TABLE IF NOT EXISTS learnings (
                learning_id TEXT PRIMARY KEY,
                trial INTEGER,
                cell_type TEXT,
                outcome TEXT,
                proof TEXT,
                supported_by TEXT,
                extracted_at TEXT
            )""",
        )
        conn.commit()
        conn.close()

    def extract_and_store(
        self,
        trial: int,
        cell_type: str,
        outcome: str,
        proof: str,
        previous_learnings: list[str] | None = None,
    ) -> list[LearningEntry]:
        previous_learnings = previous_learnings or []
        learnings: list[LearningEntry] = []

        supported_by = f"trial-{trial}:{cell_type}:{bool(outcome)}"

        if "success" in outcome.lower() or outcome == "success":
            text = f"Trial {trial}: {cell_type} succeeded with proof available"
        elif "fail" in outcome.lower():
            text = f"Trial {trial}: {cell_type} failed — review approach"
        else:
            text = f"Trial {trial}: {cell_type} completed with outcome: {outcome[:60]}"

        if previous_learnings and len(previous_learnings) > 0:
            text += f"; previous learnings: {len(previous_learnings)} entries"

        entry = LearningEntry(
            learning_id=f"learn_{trial}_{cell_type[:4]}",
            trial=trial,
            cell_type=cell_type,
            outcome=outcome[:200],
            proof=proof[:200] if proof else "",
            supported_by=supported_by,
            extracted_at=_now(),
            persisted=True,
        )
        learnings.append(entry)

        if self.db_path != ":memory:" and entry.persisted:
            conn = sqlite3.connect(self.db_path)
            conn.execute(
                "INSERT OR REPLACE INTO learnings (learning_id, trial, cell_type, outcome, proof, supported_by, extracted_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (entry.learning_id, entry.trial, entry.cell_type, entry.outcome, entry.proof, entry.supported_by, entry.extracted_at),
            )
            conn.commit()
            conn.close()

        return learnings

    def get_learnings(self, trial: int | None = None) -> list[LearningEntry]:
        if self.db_path == ":memory:":
            return []
        conn = sqlite3.connect(self.db_path)
        if trial is not None:
            rows = conn.execute("SELECT * FROM learnings WHERE trial=?", (trial,)).fetchall()
        else:
            rows = conn.execute("SELECT * FROM learnings").fetchall()
        conn.close()
        return [
            LearningEntry(
                learning_id=r[0], trial=r[1], cell_type=r[2],
                outcome=r[3], proof=r[4], supported_by=r[5], extracted_at=r[6],
                persisted=True,
            )
            for r in rows
        ]

    def learning_count(self) -> int:
        if self.db_path == ":memory:":
            return 0
        conn = sqlite3.connect(self.db_path)
        count = conn.execute("SELECT COUNT(*) FROM learnings").fetchone()[0]
        conn.close()
        return count


def extract_learning(
    cell_type: str,
    outcome: str,
    proof: str,
    previous_learnings: list[str] | None = None,
) -> list[str]:
    """Extract supported learning text from an outcome."""
    previous_learnings = previous_learnings or []
    learnings: list[str] = []

    if "success" in outcome.lower() or outcome == "success":
        learnings.append(f"{cell_type}: succeeded with verifiable proof")
    elif "fail" in outcome.lower():
        learnings.append(f"{cell_type}: failed — requires approach change")
    else:
        learnings.append(f"{cell_type}: completed — {outcome[:80]}")

    if previous_learnings:
        learnings.append(f"Context: {len(previous_learnings)} prior learnings available")

    return learnings
