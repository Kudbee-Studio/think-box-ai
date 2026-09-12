"""KUDBEE Control Fabric — Think Box handoff across execution substrates.

Work and state are portable: a Think Box can be handed off from local
process to container, microVM, or cloud GPU. Handoff preserves bindings
(identity, capabilities, state) and records the substrate transition.
"""

from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from thinkbox.workspace import ThinkBox


@dataclass
class HandoffRecord:
    handoff_id: str
    box_id: str
    from_substrate: str
    to_substrate: str
    state_hash: str
    timestamp: str
    metadata: dict[str, Any] = field(default_factory=dict)


class ThinkBoxHandoff:
    """Moves a Think Box between substrates, validating state integrity."""

    def __init__(self) -> None:
        self._records: list[HandoffRecord] = []
        self._lock = threading.Lock()

    def handoff(
        self,
        box: ThinkBox,
        to_substrate: str,
        metadata: dict[str, Any] | None = None,
    ) -> HandoffRecord:
        from_substrate = box.substrate
        state_hash = self._hash(box.snapshot())
        record = HandoffRecord(
            handoff_id=f"handoff_{uuid.uuid4().hex[:12]}",
            box_id=box.box_id,
            from_substrate=from_substrate,
            to_substrate=to_substrate,
            state_hash=state_hash,
            timestamp=datetime.now(timezone.utc).isoformat(),
            metadata=metadata or {},
        )
        box.substrate = to_substrate
        box.version += 1
        with self._lock:
            self._records.append(record)
        return record

    def verify_integrity(self, box: ThinkBox, record: HandoffRecord) -> bool:
        return self._hash(box.snapshot()) == record.state_hash

    def history(self, box_id: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        with self._lock:
            records = self._records
        if box_id:
            records = [r for r in records if r.box_id == box_id]
        return [r.__dict__ for r in records[-limit:]]

    @staticmethod
    def _hash(payload: dict[str, Any]) -> str:
        import hashlib
        import json

        stable = {k: payload[k] for k in ("owner_id", "capabilities", "policy_version", "state", "memory_refs", "artifacts") if k in payload}
        body = json.dumps(stable, sort_keys=True, default=str).encode()
        return hashlib.sha256(body).hexdigest()[:16]