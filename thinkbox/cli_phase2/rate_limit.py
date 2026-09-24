"""Rate-limit and backoff helpers (PR #178 F07)."""

from __future__ import annotations

import random
from dataclasses import dataclass


@dataclass(frozen=True)
class RateLimitAdvice:
    retry_after_s: float
    reason: str


def parse_retry_after(headers: dict[str, str]) -> RateLimitAdvice | None:
    raw = headers.get("Retry-After") or headers.get("retry-after")
    if not raw:
        return None
    try:
        seconds = float(raw.strip())
    except ValueError:
        return None
    if seconds < 0:
        return None
    return RateLimitAdvice(retry_after_s=seconds, reason="retry-after-header")


def exponential_backoff(
    attempt: int,
    base_s: float = 0.25,
    cap_s: float = 8.0,
    jitter: float = 0.1,
) -> float:
    exp = min(cap_s, base_s * (2 ** max(0, attempt)))
    if jitter <= 0:
        return exp
    return exp + random.uniform(0, jitter)
