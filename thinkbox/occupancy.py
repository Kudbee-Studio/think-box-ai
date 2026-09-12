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