"""KUDBEE Control Fabric — Admission gate.

Every side-effect request passes through the gate. It verifies the
governance token is valid and unexpired, checks the identity is registered
with the claimed capabilities, and confirms the capability is authorized.
An action without a governance token must fail closed.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from thinkbox.governance_token import GovernanceTokenService
from thinkbox.identity import IdentityLedger


@dataclass
class AdmissionDecision:
    allowed: bool
    reason: str
    agent_id: str = ""
    capability: str = ""
    timestamp: str = ""

    def __post_init__(self) -> None:
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()


@dataclass
class AdmissionRecord:
    decision: AdmissionDecision
    metadata: dict[str, Any] = field(default_factory=dict)


class AdmissionGate:
    """Authorizes side-effect requests against tokens and identities."""

    def __init__(self, tokens: GovernanceTokenService, identities: IdentityLedger) -> None:
        self._tokens = tokens
        self._identities = identities
        self._records: list[AdmissionRecord] = []
        self._lock = threading.Lock()

    def authorize(self, token_value: str, agent_id: str, capability: str, metadata: dict[str, Any] | None = None) -> AdmissionDecision:
        token = self._tokens.verify(token_value)
        if token is None:
            decision = AdmissionDecision(False, "token_invalid_or_expired", agent_id, capability)
            self._record(decision, metadata)
            return decision
        if token.agent_id != agent_id:
            decision = AdmissionDecision(False, "token_agent_mismatch", agent_id, capability)
            self._record(decision, metadata)
            return decision
        if not self._identities.has_capability(agent_id, capability):
            decision = AdmissionDecision(False, "capability_not_granted", agent_id, capability)
            self._record(decision, metadata)
            return decision
        decision = AdmissionDecision(True, "admitted", agent_id, capability)
        self._record(decision, metadata)
        return decision

    def _record(self, decision: AdmissionDecision, metadata: dict[str, Any] | None) -> None:
        with self._lock:
            self._records.append(AdmissionRecord(decision=decision, metadata=metadata or {}))

    def recent(self, limit: int = 100) -> list[dict[str, Any]]:
        with self._lock:
            return [
                {
                    "allowed": r.decision.allowed,
                    "reason": r.decision.reason,
                    "agent_id": r.decision.agent_id,
                    "capability": r.decision.capability,
                    "timestamp": r.decision.timestamp,
                }
                for r in self._records[-limit:]
            ]