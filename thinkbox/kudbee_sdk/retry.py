"""Idempotent retry policy helpers (PR #177 F06)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, TypeVar

T = TypeVar("T")


@dataclass(frozen=True)
class RetryPolicy:
    max_attempts: int
    idempotent_methods: frozenset[str]

    def should_retry(self, method: str, attempt: int, retriable: bool) -> bool:
        if attempt >= self.max_attempts:
            return False
        if not retriable:
            return False
        return method.upper() in self.idempotent_methods


def default_retry_policy(max_attempts: int = 3) -> RetryPolicy:
    return RetryPolicy(
        max_attempts=max(1, max_attempts),
        idempotent_methods=frozenset({"GET", "HEAD", "PUT", "DELETE", "OPTIONS"}),
    )


def run_with_retry(
    policy: RetryPolicy,
    method: str,
    fn: Callable[[int], T],
    is_retriable: Callable[[Exception], bool],
) -> T:
    attempt = 0
    while True:
        try:
            return fn(attempt)
        except Exception as exc:
            attempt += 1
            if not policy.should_retry(method, attempt, is_retriable(exc)):
                raise
