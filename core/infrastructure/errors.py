"""Global error handling middleware for Think Box AI.

Provides fail-safe error handling that prevents any single failure from
bringing down the entire system. All errors are logged, structured, and
returned in a consistent format.
"""

from __future__ import annotations

import functools
import traceback
from typing import Any, Callable, TypeVar

from core.foundation.error_codes import ErrorCode, error_dict
from core.foundation.logging import get_logger

logger = get_logger(__name__)

F = TypeVar("F", bound=Callable[..., Any])


def safe_call(default_return: Any = None, error_code: ErrorCode = ErrorCode.EXEC_FAILED):
    """Decorator that wraps a function to catch all exceptions.

    Never raises. Returns default_return on failure.
    """
    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            try:
                return func(*args, **kwargs)
            except Exception as e:
                logger.error(f"safe_call caught error in {func.__name__}", extra={
                    "error": str(e),
                    "traceback": traceback.format_exc(),
                })
                if isinstance(default_return, dict):
                    default_return["error"] = error_dict(error_code, str(e)).get("message")
                    default_return["error_code"] = error_code.value
                return default_return
        return wrapper
    return decorator


def async_safe_call(default_return: Any = None, error_code: ErrorCode = ErrorCode.EXEC_FAILED):
    """Async version of safe_call decorator."""
    def decorator(func: F) -> F:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                logger.error(f"async_safe_call caught error in {func.__name__}", extra={
                    "error": str(e),
                    "traceback": traceback.format_exc(),
                })
                if isinstance(default_return, dict):
                    default_return["error"] = error_dict(error_code, str(e)).get("message")
                    default_return["error_code"] = error_code.value
                return default_return
        return wrapper
    return decorator


class CircuitBreaker:
    """Prevents cascading failures by tripping after N errors."""

    def __init__(self, failure_threshold: int = 5, recovery_timeout: float = 60.0) -> None:
        self._failure_threshold = failure_threshold
        self._recovery_timeout = recovery_timeout
        self._failures = 0
        self._last_failure_time: float = 0
        self._state = "closed"  # closed, open, half-open

    @property
    def is_open(self) -> bool:
        """Check if circuit is open (failing)."""
        if self._state == "open":
            import time
            if time.monotonic() - self._last_failure_time > self._recovery_timeout:
                self._state = "half-open"
                return False
            return True
        return False

    def record_success(self) -> None:
        """Record a successful call."""
        self._failures = 0
        self._state = "closed"

    def record_failure(self) -> None:
        """Record a failed call."""
        import time
        self._failures += 1
        self._last_failure_time = time.monotonic()
        if self._failures >= self._failure_threshold:
            self._state = "open"

    def __call__(self, func: F) -> F:
        """Use as a decorator."""
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            if self.is_open:
                return {
                    "error": "Circuit breaker is open (service temporarily unavailable)",
                    "error_code": ErrorCode.PROVIDER_UNAVAILABLE.value,
                }
            try:
                result = func(*args, **kwargs)
                self.record_success()
                return result
            except Exception as e:
                self.record_failure()
                raise
        return wrapper


def health_status() -> dict[str, Any]:
    """Comprehensive health status of all subsystems."""
    from core.foundation.health import full_health_check
    from core.infrastructure.upcloud import get_client

    infra_health = full_health_check()

    # Add UpCloud health
    client = get_client()
    upcloud_health = client.health_check()

    # Overall status
    all_ok = infra_health.get("status") == "ok"
    if upcloud_health.get("status") != "ok":
        all_ok = False

    return {
        "status": "ok" if all_ok else "degraded",
        "subsystems": {
            "infrastructure": infra_health,
            "upcloud": upcloud_health,
        },
    }
