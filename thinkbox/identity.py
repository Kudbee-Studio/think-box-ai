"""KUDBEE Control Fabric — Agent identity ledger and capability scopes.

Durable authority is the first requirement of a control fabric: an agent
must know who it is, which capabilities it may exercise, and which policy
version it accepted before any side effect is permitted.
"""

from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class AgentIdentity:
    agent_id: str
    capabilities: set[str] = field(default_factory=set)
    policy_version: str = "0"
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = ""
    revoked: bool = False

    def __post_init__(self) -> None:
        if not self.created_at:
            self.created_at = datetime.now(timezone.utc).isoformat()


class IdentityLedger:
    """Registry of agent identities with immutable capability scopes."""

    def __init__(self) -> None:
        self._identities: dict[str, AgentIdentity] = {}
        self._lock = threading.Lock()

    def register(
        self,
        agent_id: str | None = None,
        capabilities: list[str] | None = None,
        policy_version: str = "0",
        metadata: dict[str, Any] | None = None,
    ) -> AgentIdentity:
        identity = AgentIdentity(
            agent_id=agent_id or f"agent_{uuid.uuid4().hex[:12]}",
            capabilities=set(capabilities or []),
            policy_version=policy_version,
            metadata=metadata or {},
        )
        with self._lock:
            self._identities[identity.agent_id] = identity
        return identity

    def get(self, agent_id: str) -> AgentIdentity | None:
        with self._lock:
            return self._identities.get(agent_id)

    def has_capability(self, agent_id: str, capability: str) -> bool:
        with self._lock:
            identity = self._identities.get(agent_id)
            if not identity or identity.revoked:
                return False
            return capability in identity.capabilities

    def grant(self, agent_id: str, capability: str) -> bool:
        with self._lock:
            identity = self._identities.get(agent_id)
            if not identity:
                return False
            identity.capabilities.add(capability)
            return True

    def revoke(self, agent_id: str) -> bool:
        with self._lock:
            identity = self._identities.get(agent_id)
            if not identity:
                return False
            identity.revoked = True
            return True

    def list(self) -> list[dict[str, Any]]:
        with self._lock:
            return [
                {
                    "agent_id": i.agent_id,
                    "capabilities": sorted(i.capabilities),
                    "policy_version": i.policy_version,
                    "revoked": i.revoked,
                }
                for i in self._identities.values()
            ]