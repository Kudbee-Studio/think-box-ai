"""Hermetic governance/orchestration clients for control-plane API (PR #154)."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any, Protocol

__all__ = (
    "AdmissionDecision",
    "CapacityGrant",
    "HermeticGovernanceClient",
    "HermeticOrchestrationClient",
    "GovernanceClientProtocol",
    "OrchestrationClientProtocol",
)


@dataclass(frozen=True)
class AdmissionDecision:
    """Result of a governance admission check."""

    allowed: bool
    reason: str = ""
    conditions: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class CapacityGrant:
    """Hermetic capacity allocation."""

    granted: bool
    allocation_id: str = ""
    resource_profile: dict[str, Any] = field(default_factory=dict)
    reason: str = ""


class GovernanceClientProtocol(Protocol):
    async def check_admission(
        self,
        action_type: str,
        action_spec: dict[str, Any],
    ) -> AdmissionDecision: ...


class OrchestrationClientProtocol(Protocol):
    async def request_capacity(
        self,
        resource_profile: dict[str, Any],
    ) -> CapacityGrant: ...

    async def release_capacity(self, allocation_id: str) -> bool: ...


class HermeticGovernanceClient:
    """Fail-closed when token missing; allow only explicit hermetic actions."""

    def __init__(self, governance_token: str | None) -> None:
        self._token = governance_token
        self.checks: int = 0
        self.denials: int = 0

    async def check_admission(
        self,
        action_type: str,
        action_spec: dict[str, Any],
    ) -> AdmissionDecision:
        self.checks += 1
        if not self._token:
            self.denials += 1
            return AdmissionDecision(allowed=False, reason="missing_governance_token")
        if action_spec.get("live_mercury"):
            self.denials += 1
            return AdmissionDecision(allowed=False, reason="live_mercury_forbidden_in_hermetic")
        if not action_type:
            self.denials += 1
            return AdmissionDecision(allowed=False, reason="empty_action_type")
        return AdmissionDecision(
            allowed=True,
            conditions={"tier": "GOVERNED", "hermetic": True},
        )


class HermeticOrchestrationClient:
    """In-process capacity grants — no HTTP."""

    def __init__(self, *, admit: bool = True) -> None:
        self._admit = admit
        self._allocations: dict[str, dict[str, Any]] = {}
        self._counter = 0

    async def request_capacity(
        self,
        resource_profile: dict[str, Any],
    ) -> CapacityGrant:
        if not self._admit:
            return CapacityGrant(granted=False, reason="capacity_denied")
        self._counter += 1
        alloc_id = f"alloc-hermetic-{self._counter}"
        profile = dict(resource_profile or {"cpu_cores": 0.5, "memory_mb": 256})
        self._allocations[alloc_id] = profile
        return CapacityGrant(
            granted=True,
            allocation_id=alloc_id,
            resource_profile=profile,
        )

    async def release_capacity(self, allocation_id: str) -> bool:
        return self._allocations.pop(allocation_id, None) is not None

    def list_allocations(self) -> dict[str, dict[str, Any]]:
        return dict(self._allocations)


def run_async(coro: Any) -> Any:
    """Run coroutine from sync test/verify paths."""
    return asyncio.get_event_loop().run_until_complete(coro)
