"""Cost tracking and model routing with fallback."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

MODEL_PRICING = {
    "gpt-4o": {"input": 2.50, "output": 10.00},
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "gpt-3.5-turbo": {"input": 0.50, "output": 1.50},
    "claude-3-5-sonnet": {"input": 3.00, "output": 15.00},
    "claude-3-opus": {"input": 15.00, "output": 75.00},
    "claude-3-haiku": {"input": 0.25, "output": 1.25},
    "llama3.1:8b": {"input": 0.0, "output": 0.0},
    "llama-3.1-8b-instant": {"input": 0.05, "output": 0.08},
    "mercury-2": {"input": 0.0, "output": 0.0},
}


@dataclass
class CostEstimate:
    tokens_input: int
    tokens_output: int
    cost_input: float
    cost_output: float
    cost_total: float
    model: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "tokens_input": self.tokens_input,
            "tokens_output": self.tokens_output,
            "cost_input": round(self.cost_input, 6),
            "cost_output": round(self.cost_output, 6),
            "cost_total": round(self.cost_total, 6),
            "model": self.model,
        }


def estimate_cost(tokens_input: int, tokens_output: int, model: str) -> CostEstimate:
    pricing = MODEL_PRICING.get(model, {"input": 0.0, "output": 0.0})
    cost_input = (tokens_input / 1_000_000) * pricing["input"]
    cost_output = (tokens_output / 1_000_000) * pricing["output"]
    return CostEstimate(
        tokens_input=tokens_input,
        tokens_output=tokens_output,
        cost_input=cost_input,
        cost_output=cost_output,
        cost_total=cost_input + cost_output,
        model=model,
    )


def estimate_tokens(text: str) -> int:
    return len(text) // 4 + 1


class BudgetManager:
    def __init__(self, max_cost_usd: float = 10.0, max_tokens: int = 1_000_000):
        self.max_cost_usd = max_cost_usd
        self.max_tokens = max_tokens
        self._spent = 0.0
        self._tokens_used = 0

    def can_spend(self, estimated_cost: float, estimated_tokens: int) -> bool:
        return (
            self._spent + estimated_cost <= self.max_cost_usd
            and self._tokens_used + estimated_tokens <= self.max_tokens
        )

    def record(self, cost: float, tokens: int) -> None:
        self._spent += cost
        self._tokens_used += tokens

    @property
    def remaining_budget(self) -> float:
        return max(0, self.max_cost_usd - self._spent)

    @property
    def remaining_tokens(self) -> int:
        return max(0, self.max_tokens - self._tokens_used)

    def to_dict(self) -> dict[str, Any]:
        return {
            "max_cost_usd": self.max_cost_usd,
            "spent_usd": round(self._spent, 6),
            "remaining_usd": round(self.remaining_budget, 6),
            "max_tokens": self.max_tokens,
            "tokens_used": self._tokens_used,
            "tokens_remaining": self.remaining_tokens,
        }


class ModelRouter:
    def __init__(self, primary_model: str, fallback_models: list[str] | None = None):
        self.primary_model = primary_model
        self.fallback_models = fallback_models or []

    def get_models(self) -> list[str]:
        return [self.primary_model] + self.fallback_models

    def get_cheapest_model(self) -> str:
        cheapest = self.primary_model
        cheapest_cost = float("inf")
        for model in self.get_models():
            pricing = MODEL_PRICING.get(model, {"input": 0.0, "output": 0.0})
            avg_cost = (pricing["input"] + pricing["output"]) / 2
            if avg_cost < cheapest_cost:
                cheapest = model
                cheapest_cost = avg_cost
        return cheapest

    def select_model(self, prefer_cheap: bool = False) -> str:
        if prefer_cheap:
            return self.get_cheapest_model()
        return self.primary_model
