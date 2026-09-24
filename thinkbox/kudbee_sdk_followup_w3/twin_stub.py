"""Digital twin stub for SDK dry-run (PR #191 F15)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class TwinState:
    twin_id: str
    attributes: dict[str, Any] = field(default_factory=dict)

    def set_attribute(self, key: str, value: Any) -> None:
        self.attributes[key] = value

    def to_document(self) -> dict[str, Any]:
        return {"twin_id": self.twin_id, "attributes": dict(self.attributes), "synced": False}


def mirror_session_to_twin(session_id: str, twin_id: str) -> TwinState:
    twin = TwinState(twin_id=twin_id)
    twin.set_attribute("session_id", session_id)
    twin.set_attribute("mode", "hermetic")
    return twin
