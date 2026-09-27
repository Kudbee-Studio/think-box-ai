"""Mesh of coupled energy loops for long-range paths (PR #193 F10)."""

from __future__ import annotations

from dataclasses import dataclass, field

from thinkbox.kudbee_sdk_followup_w3_expansion.energy_loop import EnergyLoop
from thinkbox.kudbee_sdk_followup_w3_expansion.long_range import LongRangeLink


@dataclass
class EnergyLoopMesh:
    mesh_id: str
    loops: dict[str, EnergyLoop] = field(default_factory=dict)
    links: dict[str, LongRangeLink] = field(default_factory=dict)

    def attach_loop(self, loop_id: str, capacity: float = 100.0) -> EnergyLoop:
        loop = EnergyLoop.open(loop_id, capacity_units=capacity)
        self.loops[loop_id] = loop
        return loop

    def attach_link(self, link_id: str) -> LongRangeLink:
        link = LongRangeLink.open(link_id)
        self.links[link_id] = link
        return link

    def snapshot(self) -> dict[str, object]:
        return {
            "mesh_id": self.mesh_id,
            "loop_count": len(self.loops),
            "link_count": len(self.links),
            "all_conserved": all(l.conserved() for l in self.loops.values()),
            "live_api_called": False,
            "evidence_label": "simulated",
        }
