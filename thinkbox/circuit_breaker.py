"""Circuit breaker pattern for resilient provider connections.

Implements exponential backoff with jitter and fallback to local Ollama
after consecutive failures.
"""

from __future__ import annotations

import asyncio
import logging
import random
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    """Circuit breaker states."""

    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Failing, reject requests
    HALF_OPEN = "half_open"  # Testing if service recovered


@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker."""

    failure_threshold: int = 3  # Consecutive failures to trip
    recovery_timeout: int = 60  # Seconds before half-open
    backoff_base: float = 2.0  # Base for exponential backoff (seconds)
    backoff_max: float = 32.0  # Maximum backoff (seconds)
    jitter_percent: float = 20.0  # ±% jitter on backoff


class CircuitBreaker:
    """Manages resilience with exponential backoff and circuit breaking.

    Tracks consecutive failures and switches to OPEN state after a threshold.
    In OPEN state, raises CircuitBreakerOpen immediately without trying the call.
    Enters HALF_OPEN state after recovery_timeout expires, allowing one test call.
    """

    def __init__(self, config: CircuitBreakerConfig | None = None, name: str = "default"):
        self.config = config or CircuitBreakerConfig()
        self.name = name
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.last_failure_time: float | None = None
        self.last_backoff: float = 0.0

    def record_success(self) -> None:
        """Record a successful call; reset failure counter."""
        if self.state != CircuitState.CLOSED:
            logger.info(f"[{self.name}] circuit breaker: transition OPEN/HALF_OPEN → CLOSED")
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.last_failure_time = None
        self.last_backoff = 0.0

    def record_failure(self) -> None:
        """Record a failed call; may trip the circuit."""
        self.failure_count += 1
        self.last_failure_time = time.time()

        if self.failure_count >= self.config.failure_threshold:
            old_state = self.state
            self.state = CircuitState.OPEN
            logger.warning(
                f"[{self.name}] circuit breaker TRIPPED: {self.failure_count} "
                f"consecutive failures → OPEN (recovery in {self.config.recovery_timeout}s)"
            )
            if old_state != CircuitState.OPEN:
                self._update_backoff()
        else:
            logger.debug(
                f"[{self.name}] circuit breaker: failure {self.failure_count}/"
                f"{self.config.failure_threshold}"
            )
            self._update_backoff()

    def _update_backoff(self) -> None:
        """Compute next exponential backoff with jitter."""
        # Backoff: 2^min(failure_count, log2(max_backoff / base))
        exponent = min(self.failure_count - 1, int(self.config.backoff_max / self.config.backoff_base).bit_length() - 1)
        base_backoff = self.config.backoff_base * (2 ** max(0, exponent))
        capped_backoff = min(base_backoff, self.config.backoff_max)

        # Apply jitter: ±jitter_percent
        jitter_fraction = self.config.jitter_percent / 100.0
        jitter = capped_backoff * jitter_fraction * (2 * random.random() - 1)
        self.last_backoff = max(0.1, capped_backoff + jitter)

    async def call(
        self,
        func: Callable[..., Any],
        *args: Any,
        fallback: Callable[..., Any] | None = None,
        **kwargs: Any,
    ) -> Any:
        """Execute func with circuit breaker protection.

        If circuit is OPEN and fallback is provided, calls fallback instead.
        If circuit is OPEN and no fallback, raises CircuitBreakerOpen.
        Applies backoff before retrying.
        """
        if self.state == CircuitState.OPEN:
            time_since_failure = time.time() - (self.last_failure_time or 0)
            if time_since_failure < self.config.recovery_timeout:
                if fallback:
                    logger.info(f"[{self.name}] circuit OPEN, using fallback")
                    return await self._ensure_async(fallback, *args, **kwargs)
                raise CircuitBreakerOpen(
                    f"[{self.name}] circuit breaker OPEN; retry in "
                    f"{self.config.recovery_timeout - time_since_failure:.1f}s"
                )
            else:
                logger.info(f"[{self.name}] circuit breaker: OPEN → HALF_OPEN (testing recovery)")
                self.state = CircuitState.HALF_OPEN

        # Apply backoff if retrying
        if self.failure_count > 0 and self.state == CircuitState.HALF_OPEN:
            await asyncio.sleep(self.last_backoff)

        try:
            result = await self._ensure_async(func, *args, **kwargs)
            self.record_success()
            return result
        except Exception as e:
            self.record_failure()
            raise

    @staticmethod
    async def _ensure_async(func: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        """Execute func, wrapping sync functions in to_thread."""
        if asyncio.iscoroutinefunction(func):
            return await func(*args, **kwargs)
        return await asyncio.to_thread(func, *args, **kwargs)


class CircuitBreakerOpen(RuntimeError):
    """Raised when circuit breaker is OPEN."""

    pass
