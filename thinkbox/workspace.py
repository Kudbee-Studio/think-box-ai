"""KUDBEE Control Fabric — Think Box workspace bundle.

A Think Box is a portable workspace: identity, capabilities, permissions,
durable state, memory references, and work artifacts bundled above any
model session. It survives agent failure and compute migration.
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
class ThinkBox:
    box_id: str
    owner_id: str
    capabilities: frozenset[str] = frozenset()
    policy_version: str = "0"
    state: dict[str, Any] = field(default_factory=dict)
    memory_refs: list[str] = field(default_factory=list)
    artifacts: list[str] = field(default_factory=list)
    substrate: str = "local"
    created_at: str = ""
    updated_at: str = ""
    version: int = 1

    def __post_init__(self) -> None:
        now = datetime.now(timezone.utc).isoformat()
        if not self.created_at:
            self.created_at = now
        if not self.updated_at:
            self.updated_at = now

    def snapshot(self) -> dict[str, Any]:
        return {
            "box_id": self.box_id,
            "owner_id": self.owner_id,
            "capabilities": sorted(self.capabilities),
            "policy_version": self.policy_version,
            "state": self.state,
            "memory_refs": self.memory_refs,
            "artifacts": self.artifacts,
            "substrate": self.substrate,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "version": self.version,
        }


class WorkspaceRegistry:
    """Registry of portable Think Box workspaces."""

    def __init__(self) -> None:
        self._boxes: dict[str, ThinkBox] = {}
        self._lock = threading.Lock()

    def create(
        self,
        owner_id: str,
        capabilities: list[str] | None = None,
        policy_version: str = "0",
        substrate: str = "local",
        state: dict[str, Any] | None = None,
    ) -> ThinkBox:
        box = ThinkBox(
            box_id=f"box_{uuid.uuid4().hex[:12]}",
            owner_id=owner_id,
            capabilities=frozenset(capabilities or []),
            policy_version=policy_version,
            substrate=substrate,
            state=state or {},
        )
        with self._lock:
            self._boxes[box.box_id] = box
        return box

    def get(self, box_id: str) -> ThinkBox | None:
        with self._lock:
            return self._boxes.get(box_id)

    def get_by_owner(self, owner_id: str) -> list[ThinkBox]:
        with self._lock:
            return [b for b in self._boxes.values() if b.owner_id == owner_id]

    def touch(self, box_id: str) -> bool:
        with self._lock:
            box = self._boxes.get(box_id)
            if not box:
                return False
            box.updated_at = datetime.now(timezone.utc).isoformat()
            box.version += 1
            return True

    def list(self) -> list[dict[str, Any]]:
        with self._lock:
            return [b.snapshot() for b in self._boxes.values()]


class WorkspaceStore:
    """SQLite persistence for Think Box snapshots (system of record)."""

    def __init__(self, db_path: str | Path = ":memory:") -> None:
        self._path = str(db_path)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(self._path, check_same_thread=False)
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS workspaces (
                box_id TEXT PRIMARY KEY,
                owner_id TEXT NOT NULL,
                snapshot TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        self._conn.commit()

    def save(self, box: ThinkBox) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT OR REPLACE INTO workspaces (box_id, owner_id, snapshot, updated_at) VALUES (?, ?, ?, ?)",
                (box.box_id, box.owner_id, json.dumps(box.snapshot()), box.updated_at),
            )
            self._conn.commit()

    def load(self, box_id: str) -> ThinkBox | None:
        with self._lock:
            row = self._conn.execute("SELECT snapshot FROM workspaces WHERE box_id = ?", (box_id,)).fetchone()
        if not row:
            return None
        data = json.loads(row[0])
        return ThinkBox(
            box_id=data["box_id"],
            owner_id=data["owner_id"],
            capabilities=frozenset(data["capabilities"]),
            policy_version=data["policy_version"],
            state=data["state"],
            memory_refs=data["memory_refs"],
            artifacts=data["artifacts"],
            substrate=data["substrate"],
            created_at=data["created_at"],
            updated_at=data["updated_at"],
            version=data["version"],
        )

    def load_by_owner(self, owner_id: str) -> list[ThinkBox]:
        with self._lock:
            rows = self._conn.execute("SELECT snapshot FROM workspaces WHERE owner_id = ?", (owner_id,)).fetchall()
        return [self.load(json.loads(r[0])["box_id"]) for r in rows]

    def delete(self, box_id: str) -> bool:
        with self._lock:
            cursor = self._conn.execute("DELETE FROM workspaces WHERE box_id = ?", (box_id,))
            self._conn.commit()
            return cursor.rowcount > 0

    def close(self) -> None:
        with self._lock:
            self._conn.close()