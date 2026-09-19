"""Budget-breaker: terminal receipt + reason code when budget exhausted."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from thinkbox.agent.control_plane.store import ActionReceiptStore
from thinkbox.agent.control_plane.kernel_hooks import HookContext, on_admit

logger = logging.getLogger(__name__)

BUDGET_REASON_CODES = {
    "calls_exceeded": "BudgetBreaker: call ceiling reached",
    "spend_exceeded": "BudgetBreaker: spend ceiling reached",
    "both_exceeded": "BudgetBreaker: call and spend ceilings reached",
    "invalid_budget": "BudgetBreaker: budget config invalid",
}


@dataclass
class BudgetBreakerConfig:
    max_calls: int = 100
    max_spend: float = 10.0
    calls: int = 0
    spend: float = 0.0
    cost_per_call: float = 0.01

    def is_exhausted(self) -> bool:
        return self.calls >= self.max_calls or self.spend >= self.max_spend

    def reason_code(self) -> str:
        if self.calls >= self.max_calls and self.spend >= self.max_spend:
            return "both_exceeded"
        if self.calls >= self.max_calls:
            return "calls_exceeded"
        if self.spend >= self.max_spend:
            return "spend_exceeded"
        return "invalid_budget"


class BudgetBreaker:
    """Trips a terminal receipt when budget is exhausted."""

    def __init__(self, store: ActionReceiptStore, config: BudgetBreakerConfig | None = None) -> None:
        self.store = store
        self.config = config or BudgetBreakerConfig()

    def trip(self, agent_id: str) -> dict[str, Any]:
        """Write terminal receipt if budget exhausted; return status."""
        if not self.config.is_exhausted():
            return {"tripped": False, "reason": "budget_not_exhausted"}

        code = self.config.reason_code()
        reason = BUDGET_REASON_CODES.get(code, f"BudgetBreaker: {code}")
        ctx = HookContext(
            agent_id=agent_id,
            action="budget",
            status="denied",
            reason=reason,
            evidence_label="simulated",
            metadata={"reason_code": code},
        )
        on_admit(self.store, ctx)
        logger.warning("BudgetBreaker tripped for %s: %s", agent_id, reason)
        return {"tripped": True, "reason_code": code, "reason": reason}

    def charge(self, agent_id: str) -> dict[str, Any]:
        """Charge a call; trip receipt if budget exhausted."""
        self.config.calls += 1
        self.config.spend = round(self.config.spend + self.config.cost_per_call, 6)
        result = self.trip(agent_id)
        if not result["tripped"]:
            self.store.append(
                action="budget_charge",
                status="allowed",
                reason="call charged",
                evidence_label="simulated",
                metadata={
                    "agent_id": agent_id,
                    "calls": self.config.calls,
                    "spend": self.config.spend,
                },
            )
        return result
