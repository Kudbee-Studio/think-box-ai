"""Rate-limit backoff stubs (PR #191 F07)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RateLimitState:
    remaining: int
    reset_after_ms: int


def backoff_after_429(attempt: int, base_ms: int = 100) -> int:
    return min(base_ms * (2 ** attempt), 30_000)


def parse_rate_limit_headers(headers: dict[str, str]) -> RateLimitState:
    remaining = int(headers.get("x-ratelimit-remaining", "10"))
    reset = int(headers.get("x-ratelimit-reset-ms", "1000"))
    return RateLimitState(remaining=remaining, reset_after_ms=reset)
