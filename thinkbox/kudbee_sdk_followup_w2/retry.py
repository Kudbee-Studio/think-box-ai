"""Retry policy stubs for wave 2 clients (PR #181 F06)."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TypeVar

T = TypeVar("T")


@dataclass(frozen=True)
class RetryPolicy:
    max_attempts: int
    base_delay_ms: int

    def delay_for_attempt(self, attempt: int) -> int:
        if attempt <= 0:
            return 0
        return self.base_delay_ms * (2 ** (attempt - 1))


def default_retry_policy(max_attempts: int) -> RetryPolicy:
    return RetryPolicy(max_attempts=max(1, max_attempts), base_delay_ms=50)


def run_with_retry(
    fn: Callable[[int], T],
    policy: RetryPolicy,
    is_retriable: Callable[[Exception], bool],
) -> T:
    last_exc: Exception | None = None
    for attempt in range(1, policy.max_attempts + 1):
        try:
            return fn(attempt)
        except Exception as exc:
            last_exc = exc
            if attempt >= policy.max_attempts or not is_retriable(exc):
                raise
    assert last_exc is not None
    raise last_exc
