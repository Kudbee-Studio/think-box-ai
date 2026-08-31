"""Logging configuration for THINK BOX AI.

Never logs secrets, tokens, or PII.
"""

from __future__ import annotations

import logging
import os
import sys


def setup_logging(level: str | None = None) -> logging.Logger:
    """Configure and return the root logger for the application."""
    if level is None:
        level = os.environ.get("THINKBOX_LOG_LEVEL", "INFO")

    numeric_level = getattr(logging, level.upper(), logging.INFO)

    root_logger = logging.getLogger("thinkbox")
    root_logger.setLevel(numeric_level)

    if root_logger.handlers:
        root_logger.handlers.clear()

    handler = logging.StreamHandler(sys.stderr)
    handler.setLevel(numeric_level)

    formatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )
    handler.setFormatter(formatter)
    root_logger.addHandler(handler)
    root_logger.propagate = False

    return root_logger


def get_logger(name: str) -> logging.Logger:
    """Get a child logger for a specific module."""
    return logging.getLogger(f"thinkbox.{name}")


def log_job_start(job_id: str, intent: str) -> None:
    """Log job start."""
    get_logger("job").info(f"Starting job: {job_id} — {intent}")


def log_job_end(job_id: str, verdict: str, http_calls: int, duration: float) -> None:
    """Log job completion."""
    get_logger("job").info(
        f"Completed job: {job_id} — verdict={verdict} calls={http_calls} duration={duration:.1f}s"
    )


def log_tool_call(tool_name: str, status: str) -> None:
    """Log a tool call."""
    get_logger("tool").debug(f"Tool: {tool_name} → {status}")


def log_error(msg: str, exc: Exception | None = None) -> None:
    """Log an error with optional exception."""
    if exc:
        get_logger("error").error(f"{msg}: {exc}", exc_info=True)
    else:
        get_logger("error").error(msg)
