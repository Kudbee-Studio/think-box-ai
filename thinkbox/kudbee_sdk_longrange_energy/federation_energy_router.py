"""Digital twin stub for SDK dry-run (PR #193 F15)."""

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


@dataclass
class TwinFederationStub:
    """Wave-3 federation registry (hermetic; no mesh RPC)."""

    peers: dict[str, TwinState] = field(default_factory=dict)

    def register_peer(self, twin_id: str, session_id: str) -> TwinState:
        twin = mirror_session_to_twin(session_id, twin_id)
        self.peers[twin_id] = twin
        return twin

    def federation_snapshot(self) -> dict[str, Any]:
        return {
            "peer_count": len(self.peers),
            "peers": [t.to_document() for t in self.peers.values()],
            "live_api_called": False,
            "evidence_label": "simulated",
        }


def mirror_session_to_twin(session_id: str, twin_id: str) -> TwinState:
    twin = TwinState(twin_id=twin_id)
    twin.set_attribute("session_id", session_id)
    twin.set_attribute("mode", "hermetic")
    return twin
