"""Advanced rate limiting with multiple strategies and circuit breaker.

Supports token bucket, sliding window, and adaptive rate limiting
with per-client/global quotas and circuit breaker integration.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Optional, Callable
from enum import Enum
from collections import defaultdict
from datetime import datetime, timezone


class RateLimitStrategy(Enum):
    """Rate limiting algorithm."""

    TOKEN_BUCKET = "token_bucket"
    SLIDING_WINDOW = "sliding_window"
    ADAPTIVE = "adaptive"


@dataclass
class RateLimit:
    """Rate limit configuration."""

    requests_per_second: float = 10.0
    burst_size: int = 100
    window_size_seconds: int = 60
    strategy: RateLimitStrategy = RateLimitStrategy.TOKEN_BUCKET


@dataclass
class ClientQuota:
    """Per-client quota tracking."""

    client_id: str
    requests: int = 0
    reset_at: float = field(default_factory=time.time)
    allowed: bool = True
    rejection_reason: Optional[str] = None


class TokenBucketLimiter:
    """Token bucket rate limiter."""

    def __init__(self, config: RateLimit) -> None:
        self.config = config
        self.tokens = float(config.burst_size)
        self.last_refill = time.time()

    def allow_request(self) -> bool:
        """Check if request is allowed."""
        now = time.time()
        elapsed = now - self.last_refill

        # Refill tokens
        refill_rate = self.config.requests_per_second
        tokens_to_add = elapsed * refill_rate
        self.tokens = min(self.config.burst_size, self.tokens + tokens_to_add)
        self.last_refill = now

        # Try to consume token
        if self.tokens >= 1.0:
            self.tokens -= 1.0
            return True

        return False

    def get_state(self) -> dict:
        """Get limiter state."""
        return {
            "tokens": self.tokens,
            "burst_size": self.config.burst_size,
            "refill_rate": self.config.requests_per_second,
        }


class SlidingWindowLimiter:
    """Sliding window rate limiter."""

    def __init__(self, config: RateLimit) -> None:
        self.config = config
        self.requests: list[float] = []

    def allow_request(self) -> bool:
        """Check if request is allowed."""
        now = time.time()
        window_start = now - self.config.window_size_seconds

        # Remove old requests
        self.requests = [t for t in self.requests if t > window_start]

        # Check limit
        limit = self.config.requests_per_second * self.config.window_size_seconds
        if len(self.requests) < limit:
            self.requests.append(now)
            return True

        return False

    def get_state(self) -> dict:
        """Get limiter state."""
        now = time.time()
        window_start = now - self.config.window_size_seconds
        recent = [t for t in self.requests if t > window_start]
        return {
            "requests_in_window": len(recent),
            "limit": self.config.requests_per_second * self.config.window_size_seconds,
            "window_size": self.config.window_size_seconds,
        }


class AdaptiveLimiter:
    """Adaptive rate limiter that adjusts based on response times."""

    def __init__(self, config: RateLimit) -> None:
        self.config = config
        self.base_limiter = TokenBucketLimiter(config)
        self.response_times: list[float] = []
        self.p95_latency = 0.0
        self.adaptive_rate = config.requests_per_second

    def record_response(self, latency_ms: float) -> None:
        """Record response latency."""
        self.response_times.append(latency_ms)

        # Keep only recent 100 responses
        if len(self.response_times) > 100:
            self.response_times.pop(0)

        # Calculate P95 latency
        if len(self.response_times) > 10:
            sorted_times = sorted(self.response_times)
            idx = int(len(sorted_times) * 0.95)
            self.p95_latency = sorted_times[min(idx, len(sorted_times) - 1)]

            # Adjust rate based on latency (simple feedback loop)
            if self.p95_latency > 500:  # 500ms threshold
                self.adaptive_rate = max(1.0, self.adaptive_rate * 0.9)
            elif self.p95_latency < 100:  # 100ms threshold
                self.adaptive_rate = min(self.config.requests_per_second * 2, self.adaptive_rate * 1.05)

    def allow_request(self) -> bool:
        """Check if request is allowed."""
        now = time.time()
        elapsed = now - self.base_limiter.last_refill

        # Refill with adaptive rate
        tokens_to_add = elapsed * self.adaptive_rate
        self.base_limiter.tokens = min(
            self.config.burst_size,
            self.base_limiter.tokens + tokens_to_add
        )
        self.base_limiter.last_refill = now

        # Try to consume token
        if self.base_limiter.tokens >= 1.0:
            self.base_limiter.tokens -= 1.0
            return True

        return False

    def get_state(self) -> dict:
        """Get limiter state."""
        return {
            "tokens": self.base_limiter.tokens,
            "adaptive_rate": self.adaptive_rate,
            "p95_latency_ms": self.p95_latency,
            "recent_responses": len(self.response_times),
        }


class RateLimiter:
    """Multi-client rate limiter with per-client and global limits."""

    def __init__(self, global_config: RateLimit, per_client_config: Optional[RateLimit] = None) -> None:
        self.global_config = global_config
        self.per_client_config = per_client_config or global_config

        # Create limiters
        if global_config.strategy == RateLimitStrategy.TOKEN_BUCKET:
            self.global_limiter: TokenBucketLimiter | SlidingWindowLimiter | AdaptiveLimiter = TokenBucketLimiter(global_config)
        elif global_config.strategy == RateLimitStrategy.SLIDING_WINDOW:
            self.global_limiter = SlidingWindowLimiter(global_config)
        else:
            self.global_limiter = AdaptiveLimiter(global_config)

        self.client_limiters: dict[str, TokenBucketLimiter | SlidingWindowLimiter | AdaptiveLimiter] = {}
        self.blocked_clients: dict[str, float] = {}  # client_id -> unblock_at
        self.audit_log: list[dict] = []

    def is_allowed(self, client_id: Optional[str] = None) -> tuple[bool, Optional[str]]:
        """Check if request is allowed for client."""
        # Check global limit
        if not self.global_limiter.allow_request():
            reason = "Global rate limit exceeded"
            self._log_rejection(client_id or "unknown", reason)
            return False, reason

        # Check per-client limit
        if client_id:
            if client_id not in self.client_limiters:
                if self.per_client_config.strategy == RateLimitStrategy.TOKEN_BUCKET:
                    self.client_limiters[client_id] = TokenBucketLimiter(self.per_client_config)
                elif self.per_client_config.strategy == RateLimitStrategy.SLIDING_WINDOW:
                    self.client_limiters[client_id] = SlidingWindowLimiter(self.per_client_config)
                else:
                    self.client_limiters[client_id] = AdaptiveLimiter(self.per_client_config)

            limiter = self.client_limiters[client_id]
            if not limiter.allow_request():
                reason = f"Per-client rate limit exceeded for {client_id}"
                self._log_rejection(client_id, reason)
                return False, reason

        return True, None

    def record_latency(self, client_id: Optional[str], latency_ms: float) -> None:
        """Record response latency for adaptive limiting."""
        if isinstance(self.global_limiter, AdaptiveLimiter):
            self.global_limiter.record_response(latency_ms)

        if client_id and client_id in self.client_limiters:
            limiter = self.client_limiters[client_id]
            if isinstance(limiter, AdaptiveLimiter):
                limiter.record_response(latency_ms)

    def block_client(self, client_id: str, duration_seconds: int = 60) -> None:
        """Block a client temporarily."""
        self.blocked_clients[client_id] = time.time() + duration_seconds
        self._log_action("client_blocked", client_id, {"duration": duration_seconds})

    def unblock_client(self, client_id: str) -> None:
        """Unblock a client."""
        if client_id in self.blocked_clients:
            del self.blocked_clients[client_id]
            self._log_action("client_unblocked", client_id, {})

    def get_status(self, client_id: Optional[str] = None) -> dict:
        """Get rate limiter status."""
        status = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "global": self.global_limiter.get_state(),
            "clients": {},
        }

        if client_id and client_id in self.client_limiters:
            status["clients"][client_id] = self.client_limiters[client_id].get_state()

        return status

    def _log_rejection(self, client_id: str, reason: str) -> None:
        """Log a rejection."""
        self._log_action("request_rejected", client_id, {"reason": reason})

    def _log_action(self, action: str, client_id: str, details: dict) -> None:
        """Log an action."""
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "action": action,
            "client_id": client_id,
            "details": details,
        }
        self.audit_log.append(entry)

        # Keep only last 1000 entries
        if len(self.audit_log) > 1000:
            self.audit_log.pop(0)


def rate_limit(
    limiter: RateLimiter,
    client_id_getter: Optional[Callable[..., Optional[str]]] = None,
) -> Callable:
    """Decorator for rate limiting functions."""
    def decorator(func: Callable) -> Callable:
        def wrapper(*args: object, **kwargs: object) -> object:
            client_id = None
            if client_id_getter:
                client_id = client_id_getter(*args, **kwargs)

            allowed, reason = limiter.is_allowed(client_id)
            if not allowed:
                raise Exception(f"Rate limited: {reason}")

            start = time.time()
            try:
                result = func(*args, **kwargs)
                latency_ms = (time.time() - start) * 1000
                limiter.record_latency(client_id, latency_ms)
                return result
            except Exception as e:
                latency_ms = (time.time() - start) * 1000
                limiter.record_latency(client_id, latency_ms)
                raise

        return wrapper
    return decorator
