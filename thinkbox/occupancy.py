"""KUDBEE Control Fabric — Occupancy monitors and mesh cells.

Security is occupancy, not taller walls: grounded structure (verified state,
policy, fact-cards) occupies the system's receptor sites so adversarial or
ungrounded action has nowhere clean to bind. Blast radius is contained
horizontally via peer cells sharing governance.
"""

from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


@dataclass
class OccupancySample:
    sample_id: str
    active_agents: int
    active_cells: int
    grounded_ratio: float
    load: float
    budget_spend: float
    timestamp: str
    metadata: dict[str, Any] = field(default_factory=dict)


class OccupancyMonitor:
    """Tracks system occupancy: how full the receptor fabric is.

    Occupancy expands and contracts elastically with elastic spend and
    elastic environments, side-by-side rather than vertically stacked.
    """

    def __init__(self, max_samples: int = 1000) -> None:
        self._samples: list[OccupancySample] = []
        self._max = max_samples
        self._lock = threading.Lock()
        self._active_agents = 0
        self._active_cells = 1
        self._grounded = 0
        self._total = 0

    def record_agent(self, grounded: bool) -> None:
        with self._lock:
            self._active_agents += 1
            self._total += 1
            if grounded:
                self._grounded += 1

    def release_agent(self) -> None:
        with self._lock:
            self._active_agents = max(0, self._active_agents - 1)

    def set_cells(self, count: int) -> None:
        with self._lock:
            self._active_cells = max(1, count)

    def sample(self, load: float, budget_spend: float = 0.0) -> OccupancySample:
        with self._lock:
            grounded_ratio = self._grounded / self._total if self._total else 0.0
            sample = OccupancySample(
                sample_id=f"occ_{uuid.uuid4().hex[:12]}",
                active_agents=self._active_agents,
                active_cells=self._active_cells,
                grounded_ratio=round(grounded_ratio, 4),
                load=load,
                budget_spend=budget_spend,
                timestamp=datetime.now(timezone.utc).isoformat(),
            )
            self._samples.append(sample)
            if len(self._samples) > self._max:
                self._samples.pop(0)
            return sample

    def summary(self) -> dict[str, Any]:
        with self._lock:
            return {
                "active_agents": self._active_agents,
                "active_cells": self._active_cells,
                "grounded_ratio": round(self._grounded / self._total, 4) if self._total else 0.0,
                "samples": len(self._samples),
            }


@dataclass
class MeshCell:
    cell_id: str
    name: str
    owner_id: str
    capabilities: frozenset[str] = frozenset()
    compromised: bool = False
    created_at: str = ""
    members: list[str] = field(default_factory=list)


class MeshCellManager:
    """Horizontal occupancy mesh: peer cells that share governance.

    A compromised cell must not freely inherit peer capabilities. Each cell
    isolates its own capability scope and member set.
    """

    def __init__(self) -> None:
        self._cells: dict[str, MeshCell] = {}
        self._lock = threading.Lock()

    def create(
        self,
        name: str,
        owner_id: str,
        capabilities: list[str] | None = None,
    ) -> MeshCell:
        cell = MeshCell(
            cell_id=f"cell_{uuid.uuid4().hex[:12]}",
            name=name,
            owner_id=owner_id,
            capabilities=frozenset(capabilities or []),
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        with self._lock:
            self._cells[cell.cell_id] = cell
        return cell

    def admit(self, cell_id: str, member_id: str) -> bool:
        with self._lock:
            cell = self._cells.get(cell_id)
            if not cell or cell.compromised:
                return False
            if member_id not in cell.members:
                cell.members.append(member_id)
            return True

    def expel_all(self, cell_id: str) -> bool:
        with self._lock:
            cell = self._cells.get(cell_id)
            if not cell:
                return False
            cell.compromised = True
            cell.members.clear()
            return True

    def members_in(self, cell_id: str) -> list[str]:
        with self._lock:
            cell = self._cells.get(cell_id)
            return list(cell.members) if cell else []

    def is_contained(self, cell_id: str, capability: str) -> bool:
        """True if the capability is scoped to the cell's own mesh."""
        with self._lock:
            cell = self._cells.get(cell_id)
            if not cell or cell.compromised:
                return False
            return capability in cell.capabilities

    def cell_count(self) -> int:
        with self._lock:
            return len(self._cells)