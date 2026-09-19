"""
CRDT-based Distributed ActionLedger.

Extends the local hash-chain ActionLedger with Conflict-free Replicated
Data Types for multi-node deployments. Each node appends locally and
replicates asynchronously; the CRDT merge preserves all entries from
all nodes and anchors periodic state to the local ledger for audit.
"""

from __future__ import annotations

import hashlib
import json
import logging
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

from thinkbox.ledger import ActionLedger, LedgerEntry

logger = logging.getLogger(__name__)


@dataclass
class VectorClock:
    node_id: str
    counters: dict[str, int] = field(default_factory=dict)

    def increment(self, node_id: str | None = None) -> None:
        target = node_id or self.node_id
        self.counters[target] = self.counters.get(target, 0) + 1

    def merge(self, other: VectorClock) -> None:
        for node, counter in other.counters.items():
            self.counters[node] = max(self.counters.get(node, 0), counter)

    def dominates(self, other: VectorClock) -> bool:
        for node, counter in other.counters.items():
            if self.counters.get(node, 0) < counter:
                return False
        return True

    def concurrent_with(self, other: VectorClock) -> bool:
        return not self.dominates(other) and not other.dominates(self)

    def snapshot(self) -> dict[str, Any]:
        return {"node_id": self.node_id, "counters": dict(self.counters)}


@dataclass
class CRDTEntry:
    entry_id: str
    agent_id: str
    capability: str
    action: str
    allowed: bool
    reason: str
    timestamp: str
    prev_hash: str
    entry_hash: str
    node_id: str
    vector_clock: dict[str, int] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    anchor_hash: str = ""


@dataclass
class MergeOperation:
    op_id: str
    node_id: str
    entry: CRDTEntry
    vector_clock: dict[str, int]
    timestamp: float = field(default_factory=time.time)


class DistributedActionLedger:
    """
    CRDT-based distributed action ledger.

    Properties:
    - Append-only across all nodes (CRDT LWW-Element-Set for entries)
    - Local hash chain preserved for tamper evidence
    - Periodic anchoring to local SQLite ActionLedger
    - Vector clocks for causality tracking
    - Merge resolves concurrent writes by node_id priority (deterministic)
    """

    def __init__(
        self,
        node_id: str,
        local_db_path: str | None = None,
    ) -> None:
        self.node_id = node_id
        self._local_ledger: Optional[ActionLedger] = None
        if local_db_path:
            self._local_ledger = ActionLedger(local_db_path)

        self._vector_clock = VectorClock(node_id)
        self._entries: dict[str, CRDTEntry] = {}
        self._operations: list[MergeOperation] = []
        self._lock = threading.Lock()
        self._anchored_count = 0

    @property
    def local_ledger(self) -> Optional[ActionLedger]:
        return self._local_ledger

    @property
    def vector_clock(self) -> dict[str, int]:
        return dict(self._vector_clock.counters)

    def append(
        self,
        agent_id: str,
        capability: str,
        action: str,
        allowed: bool,
        reason: str,
        metadata: dict[str, Any] | None = None,
    ) -> CRDTEntry:
        self._vector_clock.increment()
        with self._lock:
            prev_hash = self._compute_prev_hash()
            entry = CRDTEntry(
                entry_id=f"crdt_{uuid.uuid4().hex[:12]}",
                agent_id=agent_id,
                capability=capability,
                action=action,
                allowed=allowed,
                reason=reason,
                timestamp=datetime.now(timezone.utc).isoformat(),
                prev_hash=prev_hash,
                entry_hash="",
                node_id=self.node_id,
                vector_clock=dict(self._vector_clock.counters),
                metadata=metadata or {},
            )
            entry.entry_hash = self._compute_entry_hash(entry)
            self._entries[entry.entry_id] = entry

            if self._local_ledger is not None:
                try:
                    _crdt_meta = dict(metadata) if metadata else {}
                    _crdt_meta["crdt_node"] = self.node_id
                    self._local_ledger.append(
                        agent_id=agent_id,
                        capability=capability,
                        action=action,
                        allowed=allowed,
                        reason=reason,
                        metadata=_crdt_meta,
                    )
                except Exception as e:
                    logger.warning(f"Local ledger append failed: {e}")

            return entry

    def merge(self, remote_entries: list[CRDTEntry]) -> list[str]:
        """
        Merge remote CRDT entries.

        Returns list of entry_ids that were newly accepted.
        """
        accepted: list[str] = []
        with self._lock:
            for remote in remote_entries:
                self._vector_clock.merge(VectorClock(self.node_id, remote.vector_clock))
                if remote.entry_id in self._entries:
                    existing = self._entries[remote.entry_id]
                    if self._entry_priority(remote, existing) > 0:
                        self._entries[remote.entry_id] = remote
                        accepted.append(remote.entry_id)
                else:
                    self._entries[remote.entry_id] = remote
                    accepted.append(remote.entry_id)
                    self._vector_clock.increment()

        return accepted

    def anchor(self) -> Optional[str]:
        if self._local_ledger is None:
            return None
        with self._lock:
            anchor_hash = self._compute_state_hash()
            try:
                self._local_ledger.append(
                    agent_id=self.node_id,
                    capability="crdt:anchor",
                    action="anchor_state",
                    allowed=True,
                    reason=f"CRDT state anchor: {len(self._entries)} entries, {anchor_hash[:16]}",
                    metadata={
                        "entry_count": len(self._entries),
                        "state_hash": anchor_hash,
                        "vector_clock": dict(self._vector_clock.counters),
                    },
                )
                self._anchored_count += 1
                return anchor_hash
            except Exception as e:
                logger.warning(f"Anchor failed: {e}")
                return None

    def verify_local_chain(self) -> bool:
        if self._local_ledger is None:
            return True
        return self._local_ledger.verify()

    def get_entries(
        self,
        agent_id: str | None = None,
        node_id: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        with self._lock:
            entries = list(self._entries.values())
            if agent_id:
                entries = [e for e in entries if e.agent_id == agent_id]
            if node_id:
                entries = [e for e in entries if e.node_id == node_id]
            entries.sort(key=lambda e: e.timestamp)
            return [self._entry_to_dict(e) for e in entries[-limit:]]

    def entry_count(self) -> int:
        with self._lock:
            return len(self._entries)

    def anchor_count(self) -> int:
        with self._lock:
            return self._anchored_count

    def merge_operations(self) -> list[dict[str, Any]]:
        with self._lock:
            return [
                {
                    "op_id": op.op_id,
                    "node_id": op.node_id,
                    "vector_clock": op.vector_clock,
                    "timestamp": op.timestamp,
                }
                for op in self._operations
            ]

    def _compute_prev_hash(self) -> str:
        if self._local_ledger is not None:
            rows = self._local_ledger.entries(limit=1)
            if rows:
                return rows[0].get("entry_hash", "GENESIS")
        return "GENESIS"

    def _compute_entry_hash(self, entry: CRDTEntry) -> str:
        payload = {
            "entry_id": entry.entry_id,
            "agent_id": entry.agent_id,
            "capability": entry.capability,
            "action": entry.action,
            "allowed": entry.allowed,
            "reason": entry.reason,
            "timestamp": entry.timestamp,
            "prev_hash": entry.prev_hash,
            "node_id": entry.node_id,
            "vector_clock": entry.vector_clock,
            "metadata": entry.metadata,
        }
        body = json.dumps(payload, sort_keys=True, default=str).encode()
        return hashlib.sha256(body).hexdigest()[:32]

    def _compute_state_hash(self) -> str:
        entries_data = json.dumps(
            [
                {
                    "entry_id": e.entry_id,
                    "node_id": e.node_id,
                    "vector_clock": e.vector_clock,
                    "timestamp": e.timestamp,
                }
                for e in sorted(self._entries.values(), key=lambda x: x.entry_id)
            ],
            sort_keys=True,
            default=str,
        ).encode()
        return hashlib.sha256(entries_data).hexdigest()[:32]

    @staticmethod
    def _entry_priority(a: CRDTEntry, b: CRDTEntry) -> int:
        if a.entry_hash == b.entry_hash:
            return 0
        if a.node_id < b.node_id:
            return 1
        elif a.node_id > b.node_id:
            return -1
        if a.timestamp > b.timestamp:
            return 1
        elif a.timestamp < b.timestamp:
            return -1
        return 0

    @staticmethod
    def _entry_to_dict(entry: CRDTEntry) -> dict[str, Any]:
        return {
            "entry_id": entry.entry_id,
            "agent_id": entry.agent_id,
            "capability": entry.capability,
            "action": entry.action,
            "allowed": entry.allowed,
            "reason": entry.reason,
            "timestamp": entry.timestamp,
            "prev_hash": entry.prev_hash,
            "entry_hash": entry.entry_hash,
            "node_id": entry.node_id,
            "vector_clock": entry.vector_clock,
            "metadata": entry.metadata,
        }
