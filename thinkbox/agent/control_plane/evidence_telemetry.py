"""Evidence-labeled telemetry — simulated|measured labels on kernel lifecycle events."""

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class EvidenceLabel(str, Enum):
    SIMULATED = "simulated"
    MEASURED = "measured"
    INFERRED = "inferred"


@dataclass
class EvidenceEvent:
    event_type: str
    label: EvidenceLabel
    data: Dict = field(default_factory=dict)
    timestamp: float = 0.0
    agent_id: str = ""


class EvidenceTelemetry:
    """Evidence-labeled telemetry — all events tagged with evidence label."""

    def __init__(self, default_label: EvidenceLabel = EvidenceLabel.SIMULATED):
        self._default = default_label
        self._events: List[EvidenceEvent] = []

    def emit(self, event_type: str, label: Optional[EvidenceLabel] = None, data: Optional[Dict] = None, agent_id: str = "") -> EvidenceEvent:
        evt = EvidenceEvent(
            event_type=event_type,
            label=label or self._default,
            data=data or {},
            timestamp=__import__("time").time(),
            agent_id=agent_id,
        )
        self._events.append(evt)
        logger.info(f"Evidence[{evt.label.value}] {evt.event_type}")
        return evt

    def emit_lifecycle(self, old_state: str, new_state: str, label: EvidenceLabel = EvidenceLabel.SIMULATED, agent_id: str = "") -> EvidenceEvent:
        return self.emit(
            f"lifecycle:{old_state}_to_{new_state}",
            label=label, agent_id=agent_id,
            data={"from": old_state, "to": new_state},
        )

    def events(self) -> List[EvidenceEvent]:
        return list(self._events)

    def events_by_label(self, label: EvidenceLabel) -> List[EvidenceEvent]:
        return [e for e in self._events if e.label == label]

    def measured_count(self) -> int:
        return len(self.events_by_label(EvidenceLabel.MEASURED))

    def clear(self):
        self._events.clear()
