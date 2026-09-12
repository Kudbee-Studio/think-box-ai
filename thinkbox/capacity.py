"""KUDBEE Control Fabric — Elastic capacity expansion.

Occupancy expands and contracts with elastic spend and elastic
environments, side-by-side. A CapacityController admits or retires cells
based on budget availability and measured load, falling back to a floor
that preserves governance.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class CapacityDecision:
    action: str
    reason: str
    current_cells: int
    target_cells: int
    timestamp: str
    metrics: dict[str, Any] = field(default_factory=dict)


class CapacityController:
    def __init__(self, floor: int = 1, ceiling: int = 100) -> None:
        self._floor = max(1, floor)
        self._ceiling = max(self._floor, ceiling)
        self._cells = self._floor
        self._lock = threading.Lock()
        self._decisions: list[CapacityDecision] = []

    def evaluate(self, load: float, budget_spend: float, budget_limit: float) -> CapacityDecision:
        with self._lock:
            before = self._cells
            budget_ratio = budget_spend / budget_limit if budget_limit > 0 else 0.0
            if budget_ratio >= 0.9:
                self._cells = max(self._floor, self._cells - 1)
                action = "contract"
                reason = "budget_exhausted"
            elif load > 0.8 and budget_spend < budget_limit * 0.8:
                self._cells = min(self._ceiling, self._cells + 1)
                action = "expand"
                reason = "high_load_within_budget"
            elif load < 0.2 and self._cells > self._floor:
                self._cells = max(self._floor, self._cells - 1)
                action = "contract"
                reason = "low_load"
            else:
                action = "hold"
                reason = "stable"
            decision = CapacityDecision(
                action=action,
                reason=reason,
                current_cells=before,
                target_cells=self._cells,
                timestamp=datetime.now(timezone.utc).isoformat(),
                metrics={"load": load, "budget_spend": budget_spend, "budget_limit": budget_limit},
            )
            self._decisions.append(decision)
            return decision

    def current(self) -> int:
        with self._lock:
            return self._cells

    def history(self, limit: int = 50) -> list[dict[str, Any]]:
        with self._lock:
            return [d.__dict__ for d in self._decisions[-limit:]]