"""Kill-switch/quarantine durable events + query helper."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from thinkbox.agent.control_plane.store import ActionReceiptStore
from thinkbox.agent.control_plane.kernel_hooks import HookContext, on_admit

logger = logging.getLogger(__name__)


@dataclass
class KillEvent:
    event_id: str
    agent_id: str
    event_type: str
    reason: str
    timestamp: str
    evidence_label: str


class KillSwitch:
    """Durable kill-switch / quarantine events."""

    def __init__(self, store: ActionReceiptStore) -> None:
        self.store = store
        self._events: list[KillEvent] = []

    def kill(self, agent_id: str, reason: str = "manual") -> KillEvent:
        event = KillEvent(
            event_id=f"kill_{agent_id}_{int(datetime.now(timezone.utc).timestamp())}",
            agent_id=agent_id,
            event_type="kill",
            reason=reason,
            timestamp=datetime.now(timezone.utc).isoformat(),
            evidence_label="simulated",
        )
        self._persist_event(event)
        return event

    def quarantine(self, agent_id: str, reason: str = "quarantine") -> KillEvent:
        event = KillEvent(
            event_id=f"quar_{agent_id}_{int(datetime.now(timezone.utc).timestamp())}",
            agent_id=agent_id,
            event_type="quarantine",
            reason=reason,
            timestamp=datetime.now(timezone.utc).isoformat(),
            evidence_label="simulated",
        )
        self._persist_event(event)
        return event

    def _persist_event(self, event: KillEvent) -> None:
        self.store.append(
            action=f"kill_switch:{event.event_type}",
            status="denied",
            reason=event.reason,
            evidence_label=event.evidence_label,
            metadata={
                "event_id": event.event_id,
                "agent_id": event.agent_id,
                "event_type": event.event_type,
                "timestamp": event.timestamp,
            },
        )
        self._events.append(event)
        logger.warning("Kill event persisted: %s for %s", event.event_type, event.agent_id)

    def query_events(
        self,
        agent_id: str | None = None,
        event_type: str | None = None,
    ) -> list[dict[str, Any]]:
        """Query kill/quarantine events. Hermetic — no network."""
        results = list(self._events)
        if agent_id:
            results = [e for e in results if e.agent_id == agent_id]
        if event_type:
            results = [e for e in results if e.event_type == event_type]
        return [
            {
                "event_id": e.event_id,
                "agent_id": e.agent_id,
                "event_type": e.event_type,
                "reason": e.reason,
                "timestamp": e.timestamp,
                "evidence_label": e.evidence_label,
            }
            for e in results
        ]
