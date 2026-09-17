"""KUDBEE Control Fabric — GovernedEngine wrapper.

Interposes the admission gate and action ledger before any side-effect
execution that the base engine performs. Denied requests are recorded in
the ledger and surfaced as FAILED events instead of executing.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from thinkbox.admission import AdmissionGate, AdmissionDecision
from thinkbox.engine import ThinkBoxEngine, TaskState
from thinkbox.governance_token import GovernanceTokenService, TokenRequest
from thinkbox.identity import IdentityLedger
from thinkbox.ledger import ActionLedger

EXECUTION_STATUSES = (
    "FIRST_TRY_SUCCESS",
    "RECOVERED_SUCCESS",
    "FAILED_AFTER_RETRY",
    "BUDGET_EXHAUSTED",
    "UNVERIFIED",
)


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

    async def execute_verified_task(
        self,
        task_id: str,
        prompt: str,
        verify,
        reprompt,
        complete_async,
        session=None,
        agent_id: str = "",
        experiment_id: str = "",
        latency_s: float = 0.0,
        tokens: int = 0,
    ) -> dict[str, Any]:
        """Standard verified-execution wrapper around VerifiedRetrySession.

        Smallest safe integration point: every verified Think Job task runs
        here instead of calling the provider directly. Reuses
        VerifiedRetrySession/VerifiedCallResult/BudgetExhausted/RetryTrace
        without duplicating their logic. Behavior without verification is
        untouched — callers that pass verify=None get the legacy single
        attempt with status UNVERIFIED.

        Every attempt records session/job/experiment ids, taxonomy, attempt
        number, latency, usage and outcome into the ledger metadata, and the
        returned dict carries execution_status in
        FIRST_TRY_SUCCESS / RECOVERED_SUCCESS / FAILED_AFTER_RETRY /
        BUDGET_EXHAUSTED / UNVERIFIED for dashboard telemetry.
        """
        from thinkbox.pop_arena import BudgetExhausted, VerifiedRetrySession

        t0 = time.monotonic()
        if session is None:
            session = VerifiedRetrySession()
        if verify is None:
            text = await complete_async(prompt)
            status = "UNVERIFIED"
            self._ledger.append(
                agent_id=agent_id or task_id,
                capability="model:complete",
                action=f"verified_task:{task_id}",
                allowed=True,
                reason=status,
                metadata={
                    "session_id": "",
                    "job_id": task_id,
                    "experiment_id": experiment_id,
                    "taxonomy": "",
                    "attempt": 1,
                    "latency_s": round(time.monotonic() - t0, 3),
                    "tokens": tokens,
                    "outcome": status,
                },
            )
            return {
                "task_id": task_id,
                "execution_status": status,
                "valid": True,
                "taxonomy": "",
                "attempts": 1,
                "retries_used": 0,
                "converted": False,
                "latency_s": round(time.monotonic() - t0, 3),
                "tokens": tokens,
            }
        try:
            result = await session.run_async(task_id, prompt, complete_async, verify, reprompt)
        except BudgetExhausted:
            self._ledger.append(
                agent_id=agent_id or task_id,
                capability="model:complete",
                action=f"verified_task:{task_id}",
                allowed=False,
                reason="BUDGET_EXHAUSTED",
                metadata={
                    "session_id": "",
                    "job_id": task_id,
                    "experiment_id": experiment_id,
                    "taxonomy": "",
                    "attempt": session.calls_spent + 1,
                    "latency_s": round(time.monotonic() - t0, 3),
                    "tokens": tokens,
                    "outcome": "BUDGET_EXHAUSTED",
                },
            )
            return {
                "task_id": task_id,
                "execution_status": "BUDGET_EXHAUSTED",
                "valid": False,
                "taxonomy": "",
                "attempts": result_attempts(session),
                "retries_used": session.retries_fired,
                "converted": False,
                "latency_s": round(time.monotonic() - t0, 3),
                "tokens": tokens,
            }
        if result.valid and result.attempts == 1:
            status = "FIRST_TRY_SUCCESS"
        elif result.valid:
            status = "RECOVERED_SUCCESS"
        else:
            status = "FAILED_AFTER_RETRY"
        self._ledger.append(
            agent_id=agent_id or task_id,
            capability="model:complete",
            action=f"verified_task:{task_id}",
            allowed=result.valid,
            reason=status,
            metadata={
                "session_id": "",
                "job_id": task_id,
                "experiment_id": experiment_id,
                "taxonomy": result.trace.first_taxonomy,
                "final_taxonomy": result.trace.final_taxonomy,
                "attempt": result.attempts,
                "latency_s": latency_s or round(time.monotonic() - t0, 3),
                "tokens": tokens,
                "outcome": status,
            },
        )
        return {
            "task_id": task_id,
            "execution_status": status,
            "valid": result.valid,
            "taxonomy": result.trace.first_taxonomy,
            "final_taxonomy": result.trace.final_taxonomy,
            "attempts": result.attempts,
            "retries_used": result.retries_used,
            "converted": result.converted,
            "latency_s": latency_s or round(time.monotonic() - t0, 3),
            "tokens": tokens,
            "trace": result.trace.to_dict(),
        }


def result_attempts(session) -> int:
    """Attempts so far on a session (calls spent; 0 when budget blocked first call)."""
    return session.calls_spent