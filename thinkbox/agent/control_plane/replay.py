"""Deterministic replay envelope — captures inputs + receipts for replay."""

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class ReplayEvent:
    phase: str  # "INPUT" | "RECEIPT"
    action_type: str
    data: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = 0.0


@dataclass
class ReplayEnvelope:
    """Envelope holding inputs and receipts for deterministic replay."""
    agent_id: str
    events: List[ReplayEvent] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def add_input(self, action_type: str, data: Dict[str, Any]):
        self.events.append(ReplayEvent(
            phase="INPUT", action_type=action_type, data=data,
        ))

    def add_receipt(self, action_type: str, data: Dict[str, Any]):
        self.events.append(ReplayEvent(
            phase="RECEIPT", action_type=action_type, data=data,
        ))

    def events_for_action(self, action_type: str) -> List[ReplayEvent]:
        return [e for e in self.events if e.action_type == action_type]

    def to_json(self) -> str:
        return json.dumps({
            "agent_id": self.agent_id,
            "metadata": self.metadata,
            "events": [
                {
                    "phase": e.phase,
                    "action_type": e.action_type,
                    "data": e.data,
                    "timestamp": e.timestamp,
                }
                for e in self.events
            ],
        }, sort_keys=True)

    @classmethod
    def from_json(cls, s: str) -> "ReplayEnvelope":
        d = json.loads(s)
        envelope = cls(agent_id=d["agent_id"], metadata=d.get("metadata", {}))
        for e in d["events"]:
            envelope.events.append(ReplayEvent(
                phase=e["phase"], action_type=e["action_type"],
                data=e["data"], timestamp=e.get("timestamp", 0),
            ))
        return envelope

    def size(self) -> int:
        return len(self.events)
