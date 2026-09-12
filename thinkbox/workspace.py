"""KUDBEE Control Fabric — Think Box workspace bundle.

A Think Box is a portable workspace: identity, capabilities, permissions,
durable state, memory references, and work artifacts bundled above any
model session. It survives agent failure and compute migration.
"""

from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
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