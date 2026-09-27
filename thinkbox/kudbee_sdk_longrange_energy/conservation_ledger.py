"""Append-only conservation ledger for energy flow (PR #193 F11)."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ConservationEntry:
    loop_id: str
    delta_units: float
    conserved: bool


@dataclass
class ConservationLedger:
    entries: list[ConservationEntry] = field(default_factory=list)

    def record(self, loop_id: str, delta_units: float, conserved: bool) -> ConservationEntry:
        entry = ConservationEntry(loop_id=loop_id, delta_units=delta_units, conserved=conserved)
        self.entries.append(entry)
        return entry

    def verify_chain(self) -> bool:
        return all(e.conserved for e in self.entries)

    def summary(self) -> dict[str, object]:
        return {
            "entry_count": len(self.entries),
            "chain_ok": self.verify_chain(),
            "live_api_called": False,
        }
