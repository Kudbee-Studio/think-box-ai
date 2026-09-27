"""Quantitative free-flowing energy loop accounting (hermetic, PR #192)."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class EnergyLoop:
    loop_id: str
    capacity_units: float
    flow_units: float = 0.0
    events: list[dict[str, float]] = field(default_factory=list)

    @classmethod
    def open(cls, loop_id: str, capacity_units: float = 1000.0) -> EnergyLoop:
        return cls(loop_id=loop_id, capacity_units=capacity_units)

    def deposit(self, amount: float) -> None:
        if amount < 0:
            raise ValueError("deposit must be non-negative")
        self.flow_units += amount
        self.events.append({"deposit": amount})

    def conserved(self) -> bool:
        return self.flow_units <= self.capacity_units

    def free_flow_rate(self) -> float:
        if not self.events:
            return 0.0
        return self.flow_units / len(self.events)

    def snapshot(self) -> dict[str, object]:
        return {
            "loop_id": self.loop_id,
            "flow_units": self.flow_units,
            "capacity_units": self.capacity_units,
            "conserved": self.conserved(),
            "free_flow_rate": self.free_flow_rate(),
            "live_api_called": False,
            "evidence_label": "simulated",
        }
