"""Deterministic backoff schedule for hermetic retries (PR #183 F12)."""

from __future__ import annotations


def backoff_delay_ms(attempt: int, base_ms: int = 50, cap_ms: int = 500) -> int:
    if attempt < 1:
        attempt = 1
    delay = base_ms * (2 ** (attempt - 1))
    return min(delay, cap_ms)


def backoff_schedule(max_attempts: int) -> tuple[int, ...]:
    return tuple(backoff_delay_ms(i) for i in range(1, max_attempts + 1))
