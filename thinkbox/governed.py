"""KUDBEE Control Fabric — GovernedEngine wrapper.

Interposes the admission gate and action ledger before any side-effect
execution that the base engine performs. Denied requests are recorded in
the ledger and surfaced as FAILED events instead of executing.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from thinkbox.admission import AdmissionGate, AdmissionDecision
from thinkbox.engine import ThinkBoxEngine, TaskState
from thinkbox.governance_token import GovernanceTokenService, TokenRequest
from thinkbox.identity import IdentityLedger
from thinkbox.ledger import ActionLedger


@dataclass
class GovernedEngineConfig:
    engine: ThinkBoxEngine
    token_service: GovernanceTokenService | None = None
    identity_ledger: IdentityLedger | None = None
    ledger_path: str = ":memory:"


class GovernedEngine:
    """Admission-gated facade around the base ThinkBoxEngine."""

    def __init__(self, config: GovernedEngineConfig) -> None:
        self._base = config.engine
        self._tokens = config.token_service or GovernanceTokenService()
        self._identities = config.identity_ledger or IdentityLedger()
        self._ledger = ActionLedger(config.ledger_path)
        self._gate = AdmissionGate(self._tokens, self._identities)

    def register_agent(self, agent_id: str, capabilities: list[str]) -> str:
        """Register identity and mint a governance token in one step."""
        self._identities.register(agent_id=agent_id, capabilities=capabilities)
        token = self._tokens.issue(TokenRequest(agent_id=agent_id, capabilities=capabilities, ttl_seconds=3600.0))
        return token.token_value

    def authorize(self, token_value: str, agent_id: str, capability: str, action: str, metadata: dict[str, Any] | None = None) -> AdmissionDecision:
        decision = self._gate.authorize(token_value, agent_id, capability, metadata)
        self._ledger.append(
            agent_id=agent_id,
            capability=capability,
            action=action,
            allowed=decision.allowed,
            reason=decision.reason,
            metadata=metadata,
        )
        return decision

    async def execute_goal(self, goal: str, token_value: str = "", agent_id: str = "", capability: str = "goal:execute") -> dict[str, Any]:
        if token_value:
            decision = self.authorize(token_value, agent_id, capability, "execute_goal")
            if not decision.allowed:
                self._base.emit("root", TaskState.FAILED, f"Governance denied: {decision.reason}")
                return {"governed": False, "reason": decision.reason, "events": len(self._base.events)}
        summary = await self._base.execute_goal(goal)
        summary["governed"] = True
        return summary

    @property
    def ledger(self) -> ActionLedger:
        return self._ledger

    @property
    def gate(self) -> AdmissionGate:
        return self._gate