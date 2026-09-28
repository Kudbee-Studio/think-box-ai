"""Centralized error handling and recovery patterns.

Provides structured error types, recovery strategies, and audit logging
for all failures in the Think Box AI system.
"""

from __future__ import annotations

import json
import logging
import traceback
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Optional, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


class ErrorSeverity(Enum):
    """Error severity levels for routing and alerting."""

    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class ErrorRecoveryStrategy(Enum):
    """Recovery strategies when errors occur."""

    RETRY = "retry"  # Retry with backoff
    FALLBACK = "fallback"  # Use fallback value
    ESCALATE = "escalate"  # Escalate to human
    FAIL_CLOSED = "fail_closed"  # Explicit failure
    IGNORE = "ignore"  # Log and continue


@dataclass
class ErrorContext:
    """Structured error context for audit and recovery."""

    error_type: str
    message: str
    severity: ErrorSeverity
    recovery_strategy: ErrorRecoveryStrategy
    agent_id: Optional[str] = None
    task_id: Optional[str] = None
    think_box_id: Optional[str] = None
    timestamp: Optional[str] = None
    stack_trace: Optional[str] = None
    context_data: Optional[dict[str, Any]] = None

    def __post_init__(self):
        """Normalize timestamp."""
        if self.timestamp is None:
            self.timestamp = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable dict."""
        data = asdict(self)
        data["severity"] = self.severity.value
        data["recovery_strategy"] = self.recovery_strategy.value
        return data

    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict())

    def audit_log(self) -> None:
        """Write to audit log."""
        logger.error(f"Error audit: {self.to_json()}")


class ThinkBoxError(Exception):
    """Base exception for all Think Box errors."""

    def __init__(
        self,
        message: str,
        *,
        severity: ErrorSeverity = ErrorSeverity.ERROR,
        recovery_strategy: ErrorRecoveryStrategy = ErrorRecoveryStrategy.FAIL_CLOSED,
        agent_id: Optional[str] = None,
        task_id: Optional[str] = None,
        think_box_id: Optional[str] = None,
        context_data: Optional[dict[str, Any]] = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.severity = severity
        self.recovery_strategy = recovery_strategy
        self.agent_id = agent_id
        self.task_id = task_id
        self.think_box_id = think_box_id
        self.context_data = context_data or {}
        self.timestamp = datetime.now(timezone.utc).isoformat()

    def to_context(self) -> ErrorContext:
        """Convert to ErrorContext for audit logging."""
        return ErrorContext(
            error_type=self.__class__.__name__,
            message=self.message,
            severity=self.severity,
            recovery_strategy=self.recovery_strategy,
            agent_id=self.agent_id,
            task_id=self.task_id,
            think_box_id=self.think_box_id,
            timestamp=self.timestamp,
            stack_trace=traceback.format_exc(),
            context_data=self.context_data,
        )

    def audit_log(self) -> None:
        """Write to audit log."""
        self.to_context().audit_log()


class ModelCallError(ThinkBoxError):
    """Error during model inference."""

    def __init__(
        self,
        message: str,
        *,
        provider: str = "unknown",
        model: str = "unknown",
        retryable: bool = False,
        **kwargs: Any,
    ) -> None:
        kwargs.setdefault(
            "recovery_strategy",
            ErrorRecoveryStrategy.RETRY if retryable else ErrorRecoveryStrategy.FAIL_CLOSED,
        )
        super().__init__(message, **kwargs)
        self.provider = provider
        self.model = model
        self.retryable = retryable
        self.context_data.update({"provider": provider, "model": model, "retryable": retryable})


class MemoryError(ThinkBoxError):
    """Error accessing or writing memory."""

    def __init__(self, message: str, **kwargs: Any) -> None:
        kwargs.setdefault("severity", ErrorSeverity.WARNING)
        kwargs.setdefault("recovery_strategy", ErrorRecoveryStrategy.RETRY)
        super().__init__(message, **kwargs)


class GovernanceError(ThinkBoxError):
    """Error in governance or admission."""

    def __init__(
        self, message: str, *, reason: str = "unknown", **kwargs: Any
    ) -> None:
        kwargs.setdefault("severity", ErrorSeverity.WARNING)
        kwargs.setdefault("recovery_strategy", ErrorRecoveryStrategy.ESCALATE)
        super().__init__(message, **kwargs)
        self.reason = reason
        self.context_data["reason"] = reason


class NetworkError(ThinkBoxError):
    """Network-related error (timeout, connection refused, etc)."""

    def __init__(
        self, message: str, *, retryable: bool = True, **kwargs: Any
    ) -> None:
        kwargs.setdefault(
            "recovery_strategy",
            ErrorRecoveryStrategy.RETRY if retryable else ErrorRecoveryStrategy.FAIL_CLOSED,
        )
        super().__init__(message, **kwargs)
        self.retryable = retryable
        self.context_data["retryable"] = retryable


class ValidationError(ThinkBoxError):
    """Data validation error."""

    def __init__(
        self, message: str, *, field: Optional[str] = None, **kwargs: Any
    ) -> None:
        kwargs.setdefault("severity", ErrorSeverity.WARNING)
        kwargs.setdefault("recovery_strategy", ErrorRecoveryStrategy.FAIL_CLOSED)
        super().__init__(message, **kwargs)
        self.field = field
        if field:
            self.context_data["field"] = field


def with_recovery(
    strategy: ErrorRecoveryStrategy = ErrorRecoveryStrategy.FAIL_CLOSED,
    fallback: Optional[T] = None,
    max_retries: int = 3,
) -> Callable:
    """Decorator for error recovery strategies.

    Args:
        strategy: Recovery strategy to use
        fallback: Fallback value to return on failure (for FALLBACK strategy)
        max_retries: Max retries for RETRY strategy

    Example:
        @with_recovery(ErrorRecoveryStrategy.RETRY, max_retries=5)
        async def call_model():
            return await client.generate("prompt")
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        async def async_wrapper(*args: Any, **kwargs: Any) -> T:
            if strategy == ErrorRecoveryStrategy.RETRY:
                for attempt in range(max_retries):
                    try:
                        return await func(*args, **kwargs)
                    except ThinkBoxError as e:
                        # Always retry for first max_retries-1 attempts
                        if attempt == max_retries - 1:
                            e.audit_log()
                            raise
                        logger.warning(
                            f"Retrying {func.__name__} (attempt {attempt + 1}/{max_retries}): {e.message}"
                        )
                raise ThinkBoxError(f"Max retries exceeded for {func.__name__}")

            elif strategy == ErrorRecoveryStrategy.FALLBACK:
                try:
                    return await func(*args, **kwargs)
                except ThinkBoxError as e:
                    if fallback is not None:
                        logger.warning(f"Using fallback for {func.__name__}: {e.message}")
                        return fallback
                    e.audit_log()
                    raise

            else:  # FAIL_CLOSED
                try:
                    return await func(*args, **kwargs)
                except ThinkBoxError as e:
                    e.audit_log()
                    raise

        def sync_wrapper(*args: Any, **kwargs: Any) -> T:
            if strategy == ErrorRecoveryStrategy.RETRY:
                for attempt in range(max_retries):
                    try:
                        return func(*args, **kwargs)
                    except ThinkBoxError as e:
                        # Always retry for first max_retries-1 attempts
                        if attempt == max_retries - 1:
                            e.audit_log()
                            raise
                        logger.warning(
                            f"Retrying {func.__name__} (attempt {attempt + 1}/{max_retries}): {e.message}"
                        )
                raise ThinkBoxError(f"Max retries exceeded for {func.__name__}")

            elif strategy == ErrorRecoveryStrategy.FALLBACK:
                try:
                    return func(*args, **kwargs)
                except ThinkBoxError as e:
                    if fallback is not None:
                        logger.warning(f"Using fallback for {func.__name__}: {e.message}")
                        return fallback
                    e.audit_log()
                    raise

            else:  # FAIL_CLOSED
                try:
                    return func(*args, **kwargs)
                except ThinkBoxError as e:
                    e.audit_log()
                    raise

        # Return appropriate wrapper
        import inspect

        if inspect.iscoroutinefunction(func):
            return async_wrapper  # type: ignore
        else:
            return sync_wrapper  # type: ignore

    return decorator
