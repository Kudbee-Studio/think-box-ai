"""Budget breaker: hard $/token budget enforcement — trip releases capacity and halts."""

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


@dataclass
class BudgetState:
    spent: float = 0.0
    limit: float = 0.0
    currency: str = "usd"
    trip: bool = False


class BudgetBreaker:
    """Hard budget breaker. When spent exceeds limit: trip → release capacity + halt."""

    def __init__(self, limit: float, currency: str = "usd"):
        self.limit = limit
        self.currency = currency
        self.state = BudgetState(limit=limit, currency=currency)
        self._on_trip: Optional[Any] = None  # callback(agent_id, reason)

    def set_trip_callback(self, cb: Any):
        """Set callback called when budget trips: cb(agent_id, reason)."""
        self._on_trip = cb

    def record_spend(self, amount: float, agent_id: str) -> bool:
        """Record spend. Returns False if budget tripped (halt)."""
        if self.state.trip:
            return False
        self.state.spent += amount
        if self.state.spent > self.limit:
            self._trip(agent_id)
            return False
        return True

    def _trip(self, agent_id: str):
        self.state.trip = True
        reason = f"budget exhausted: {self.state.spent:.4f} > {self.limit:.4f} {self.currency}"
        logger.warning(f"Budget tripped for {agent_id}: {reason}")
        if self._on_trip:
            try:
                if asyncio.iscoroutinefunction(self._on_trip):
                    asyncio.create_task(self._on_trip(agent_id, reason))
                else:
                    self._on_trip(agent_id, reason)
            except Exception as e:
                logger.error(f"Trip callback error: {e}")

    def can_spend(self, amount: float) -> bool:
        """Check if spending amount would exceed remaining budget."""
        if self.state.trip:
            return False
        return (self.state.spent + amount) <= self.limit

    def remaining(self) -> float:
        return max(0.0, self.limit - self.state.spent)

    def reset(self):
        """Reset budget (for testing / replay)."""
        self.state.spent = 0.0
        self.state.trip = False
