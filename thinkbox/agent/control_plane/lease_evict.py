"""Lease expiry → durable eviction receipt."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from thinkbox.agent.control_plane.store import ActionReceiptStore
from thinkbox.agent.control_plane.kernel_hooks import HookContext, on_admit

logger = logging.getLogger(__name__)


@dataclass
class Lease:
    agent_id: str
    lease_id: str
    expires_at: str
    metadata: dict[str, Any] = field(default_factory=dict)


class LeaseEvictor:
    """Monitors leases and writes durable eviction receipts on expiry."""

    def __init__(self, store: ActionReceiptStore) -> None:
        self.store = store
        self._leases: dict[str, Lease] = {}

    def register_lease(self, lease: Lease) -> None:
        self._leases[lease.lease_id] = lease
        logger.info("Lease registered: %s for %s", lease.lease_id, lease.agent_id)

    def check_expired(self) -> list[dict[str, Any]]:
        """Check for expired leases and write eviction receipts."""
        now = datetime.now(timezone.utc)
        evictions: list[dict[str, Any]] = []
        expired_ids = []

        for lease_id, lease in self._leases.items():
            expires = datetime.fromisoformat(lease.expires_at)
            if expires <= now:
                expired_ids.append(lease_id)
                ctx = HookContext(
                    agent_id=lease.agent_id,
                    action="lease_evict",
                    status="denied",
                    reason=f"lease expired: {lease.expires_at}",
                    evidence_label="simulated",
                    metadata={
                        "lease_id": lease_id,
                        "agent_id": lease.agent_id,
                        "expires_at": lease.expires_at,
                    },
                )
                on_admit(self.store, ctx)
                evictions.append({
                    "lease_id": lease_id,
                    "agent_id": lease.agent_id,
                    "reason": f"lease expired: {lease.expires_at}",
                })

        for lease_id in expired_ids:
            del self._leases[lease_id]

        return evictions

    def active_leases(self) -> list[Lease]:
        now = datetime.now(timezone.utc)
        active: list[Lease] = []
        for lease_id, lease in self._leases.items():
            expires = datetime.fromisoformat(lease.expires_at)
            if expires > now:
                active.append(lease)
        return active
