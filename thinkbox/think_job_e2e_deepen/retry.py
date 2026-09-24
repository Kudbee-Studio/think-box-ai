"""Retry policy stub for hermetic job steps (PR #183 F11)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class RetryDecision:
    should_retry: bool
    attempt: int
    reason: str


def should_retry_step(
    taxonomy: str,
    attempt: int,
    max_attempts: int = 2,
) -> RetryDecision:
    retryable = taxonomy in ("transient", "distractor-compliance", "rate_limited_stub")
    if attempt >= max_attempts:
        return RetryDecision(False, attempt, "max_attempts")
    if retryable:
        return RetryDecision(True, attempt + 1, "retryable_taxonomy")
    return RetryDecision(False, attempt, "non_retryable")


def apply_retry_stub(action: dict[str, Any]) -> dict[str, Any]:
    decision = should_retry_step(str(action.get("taxonomy", "")), int(action.get("attempt", 1)))
    return {
        "action": action.get("action"),
        "should_retry": decision.should_retry,
        "next_attempt": decision.attempt,
        "reason": decision.reason,
        "live_api_called": False,
    }
