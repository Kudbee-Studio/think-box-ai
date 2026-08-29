"""Circuit breaker for provider resilience.

State machine: CLOSED -> OPEN -> HALF_OPEN -> CLOSED
- CLOSED: Normal operation, requests pass through
- OPEN: Failing, requests immediately rejected
- HALF_OPEN: Testing recovery, limited requests pass through
"""

from __future__ import annotations
import time
import threading
import logging
from enum import Enum
from typing import Any, Callable, TypeVar

from core.foundation.error_codes import ErrorCode, format_error_response
from core.foundation.errors import ProviderError

logger = logging.getLogger(__name__)

T = TypeVar("T")


class CircuitState(str, Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreaker:
    """Thread-safe circuit breaker for external service calls.
    
    Time Complexity: O(1) per call
    Space Complexity: O(1) per breaker instance
    """

    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout: float = 30.0,
        half_open_max_calls: int = 3,
    ) -> None:
        self._name = name
        self._failure_threshold = failure_threshold
        self._recovery_timeout = recovery_timeout
        self._half_open_max_calls = half_open_max_calls

        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time: float = 0
        self._half_open_calls = 0
        self._lock = threading.Lock()

    @property
    def state(self) -> CircuitState:
        with self._lock:
            if self._state == CircuitState.OPEN:
                if time.monotonic() - self._last_failure_time >= self._recovery_timeout:
                    self._state = CircuitState.HALF_OPEN
                    self._half_open_calls = 0
                    logger.info("Circuit '%s' transitioning to HALF_OPEN", self._name)
            return self._state

    def record_success(self) -> None:
        with self._lock:
            if self._state == CircuitState.HALF_OPEN:
                self._success_count += 1
                if self._success_count >= self._half_open_max_calls:
                    self._state = CircuitState.CLOSED
                    self._failure_count = 0
                    self._success_count = 0
                    logger.info("Circuit '%s' recovered -> CLOSED", self._name)
            else:
                self._failure_count = 0

    def record_failure(self) -> None:
        with self._lock:
            self._failure_count += 1
            self._last_failure_time = time.monotonic()
            if self._state == CircuitState.HALF_OPEN:
                self._state = CircuitState.OPEN
                logger.warning("Circuit '%s' re-opened from HALF_OPEN", self._name)
            elif self._failure_count >= self._failure_threshold:
                self._state = CircuitState.OPEN
                logger.warning(
                    "Circuit '%s' tripped OPEN after %d failures",
                    self._name, self._failure_count
                )

    def allow_request(self) -> bool:
        state = self.state
        if state == CircuitState.CLOSED:
            return True
        if state == CircuitState.HALF_OPEN:
            with self._lock:
                if self._half_open_calls < self._half_open_max_calls:
                    self._half_open_calls += 1
                    return True
            return False
        return False  # OPEN

    async def call(self, func: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        """Execute function through circuit breaker."""
        if not self.allow_request():
            raise ProviderError(
                format_error_response(
                    ErrorCode.PROVIDER_UNAVAILABLE,
                    f"Circuit breaker '{self._name}' is OPEN",
                    circuit_state=self._state.value,
                    retry_after=self._recovery_timeout,
                )["message"]
            )

        try:
            result = await func(*args, **kwargs)
            self.record_success()
            return result
        except Exception as exc:
            self.record_failure()
            raise

    def get_status(self) -> dict[str, Any]:
        return {
            "name": self._name,
            "state": self.state.value,
            "failure_count": self._failure_count,
            "last_failure_time": self._last_failure_time,
        }


class CircuitBreakerRegistry:
    """Global registry of circuit breakers per provider."""

    _breakers: dict[str, CircuitBreaker] = {}
    _lock = threading.Lock()

    @classmethod
    def get(cls, name: str, **kwargs: Any) -> CircuitBreaker:
        with cls._lock:
            if name not in cls._breakers:
                cls._breakers[name] = CircuitBreaker(name, **kwargs)
            return cls._breakers[name]

    @classmethod
    def get_all(cls) -> dict[str, dict[str, Any]]:
        return {name: cb.get_status() for name, cb in cls._breakers.items()}
