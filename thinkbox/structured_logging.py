"""Structured logging for observability and auditing.

Provides RFC 3339 timestamps, JSON output, and contextual information
for all operations in the Think Box AI system.
"""

from __future__ import annotations

import json
import logging
import logging.config
import sys
from datetime import datetime, timezone
from typing import Any, Optional


class StructuredFormatter(logging.Formatter):
    """JSON formatter for structured logging with RFC 3339 timestamps."""

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        log_data = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        # Add extra fields if present
        for key, value in record.__dict__.items():
            if key not in (
                "name",
                "msg",
                "args",
                "created",
                "filename",
                "funcName",
                "levelname",
                "levelno",
                "lineno",
                "module",
                "msecs",
                "message",
                "pathname",
                "process",
                "processName",
                "relativeCreated",
                "thread",
                "threadName",
                "exc_info",
                "exc_text",
                "stack_info",
            ):
                log_data[key] = value

        return json.dumps(log_data)


class ContextualLogger:
    """Logger with automatic context tracking."""

    def __init__(self, logger: logging.Logger) -> None:
        self.logger = logger
        self._context: dict[str, Any] = {}

    def set_context(self, **kwargs: Any) -> None:
        """Set contextual information (agent_id, task_id, etc)."""
        self._context.update(kwargs)

    def clear_context(self) -> None:
        """Clear all context."""
        self._context.clear()

    def _log(
        self,
        level: int,
        message: str,
        *,
        exc_info: bool = False,
        extra: Optional[dict[str, Any]] = None,
    ) -> None:
        """Internal logging with context."""
        log_data = dict(self._context)
        if extra:
            log_data.update(extra)

        self.logger.log(level, message, extra=log_data, exc_info=exc_info)

    def debug(self, message: str, *, extra: Optional[dict[str, Any]] = None) -> None:
        """Log debug message."""
        self._log(logging.DEBUG, message, extra=extra)

    def info(self, message: str, *, extra: Optional[dict[str, Any]] = None) -> None:
        """Log info message."""
        self._log(logging.INFO, message, extra=extra)

    def warning(self, message: str, *, extra: Optional[dict[str, Any]] = None) -> None:
        """Log warning message."""
        self._log(logging.WARNING, message, extra=extra)

    def error(
        self,
        message: str,
        *,
        exc_info: bool = False,
        extra: Optional[dict[str, Any]] = None,
    ) -> None:
        """Log error message."""
        self._log(logging.ERROR, message, exc_info=exc_info, extra=extra)

    def critical(
        self,
        message: str,
        *,
        exc_info: bool = False,
        extra: Optional[dict[str, Any]] = None,
    ) -> None:
        """Log critical message."""
        self._log(logging.CRITICAL, message, exc_info=exc_info, extra=extra)


def configure_structured_logging(
    level: int = logging.INFO,
    output: str = "stdout",
    json_format: bool = True,
) -> None:
    """Configure structured logging for the application.

    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        output: Output destination ('stdout' or 'stderr')
        json_format: Use JSON format (True) or plain text (False)
    """
    # Get root logger
    root = logging.getLogger()
    root.setLevel(level)

    # Remove existing handlers
    root.handlers.clear()

    # Create formatter
    if json_format:
        formatter = StructuredFormatter()
    else:
        formatter = logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%SZ",
        )

    # Create handler
    handler = logging.StreamHandler(sys.stdout if output == "stdout" else sys.stderr)
    handler.setFormatter(formatter)
    root.addHandler(handler)

    # Set level for handler
    handler.setLevel(level)

    # Suppress overly verbose loggers
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.WARNING)


def get_contextual_logger(name: str) -> ContextualLogger:
    """Get a contextual logger instance.

    Args:
        name: Logger name (typically __name__)

    Returns:
        ContextualLogger instance with context tracking
    """
    logger = logging.getLogger(name)
    return ContextualLogger(logger)


# Example usage function
def example_usage() -> None:
    """Example of using structured logging."""
    configure_structured_logging(level=logging.DEBUG, json_format=True)

    logger = get_contextual_logger(__name__)
    logger.set_context(agent_id="agent-001", task_id="task-123")

    logger.info("Operation started", extra={"operation": "inference"})
    logger.debug("Debug information", extra={"param": "value"})
    logger.warning("Warning occurred", extra={"issue": "slow"})
    logger.error("Error occurred", extra={"error_code": "E001"})

    logger.clear_context()
    logger.info("Context cleared")


if __name__ == "__main__":
    example_usage()
