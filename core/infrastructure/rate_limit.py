"""Token bucket rate limiting for API endpoints."""

from __future__ import annotations
import time
import threading
from typing import Dict, Tuple
from core.foundation.error_codes import ErrorCode, format_error_response


class RateLimitExceeded(Exception):
    """Raised when a client exceeds their rate limit."""
    pass


class TokenBucket:
    """Thread-safe token bucket rate limiter.
    
    Time Complexity: O(1) per check
    Space Complexity: O(C) where C = number of tracked clients
    """

    def __init__(self, rate: float = 10.0, burst: int = 20) -> None:
        self._rate = rate
        self._burst = burst
        self._clients: Dict[str, Tuple[float, float]] = {}
        self._lock = threading.Lock()

    def allow(self, client_id: str) -> bool:
        """Check if request is allowed under rate limit."""
        now = time.monotonic()
        
        with self._lock:
            if client_id not in self._clients:
                self._clients[client_id] = (now, self._burst - 1)
                return True
            
            last_time, tokens = self._clients[client_id]
            elapsed = now - last_time
            tokens = min(self._burst, tokens + elapsed * self._rate)
            
            if tokens >= 1.0:
                self._clients[client_id] = (now, tokens - 1.0)
                return True
            
            self._clients[client_id] = (now, tokens)
            return False

    def retry_after(self, client_id: str) -> float:
        """Calculate seconds until next request allowed."""
        with self._lock:
            if client_id not in self._clients:
                return 0.0
            _, tokens = self._clients[client_id]
            if tokens >= 1.0:
                return 0.0
            return (1.0 - tokens) / self._rate


class RateLimiter:
    """Multi-tier rate limiter with per-endpoint configuration."""

    def __init__(self) -> None:
        self._buckets: Dict[str, TokenBucket] = {
            "default": TokenBucket(rate=10.0, burst=20),
            "exec": TokenBucket(rate=5.0, burst=10),
            "chat": TokenBucket(rate=3.0, burst=5),
        }

    def check(self, client_id: str, endpoint: str = "default") -> None:
        """Check rate limit for client on endpoint. Raises if exceeded."""
        bucket = self._buckets.get(endpoint, self._buckets["default"])
        if not bucket.allow(client_id):
            retry = bucket.retry_after(client_id)
            raise RateLimitExceeded(
                format_error_response(
                    ErrorCode.PROVIDER_RATE_LIMIT,
                    f"Rate limit exceeded. Retry after {retry:.1f}s",
                    retry_after_seconds=round(retry, 2),
                    endpoint=endpoint
                )["message"]
            )
