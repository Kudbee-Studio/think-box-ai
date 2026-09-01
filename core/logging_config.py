"""Structured logging for Think Box AI.

JSON-formatted logs with levels, timestamps, and context.
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone
from typing import Any


class JSONFormatter(logging.Formatter):
    """Format logs as JSON."""

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        if hasattr(record, "extra"):
            log_entry["extra"] = record.extra
        return json.dumps(log_entry)


def setup_logging(level: str = "INFO") -> logging.Logger:
    """Configure structured logging."""
    root_logger = logging.getLogger("thinkbox")
    root_logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    if not root_logger.handlers:
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(JSONFormatter())
        root_logger.addHandler(handler)
        root_logger.propagate = False

    return root_logger


def get_logger(name: str) -> logging.Logger:
    """Get a child logger."""
    return logging.getLogger(f"thinkbox.{name}")


def log_job_start(job_id: str, intent: str):
    get_logger("job").info(f"Starting job: {job_id}", extra={"job_id": job_id, "intent": intent})


def log_job_end(job_id: str, verdict: str, duration: float):
    get_logger("job").info(f"Completed job: {job_id}", extra={"job_id": job_id, "verdict": verdict, "duration": duration})


def log_tool_call(tool_name: str, status: str):
    get_logger("tool").debug(f"Tool: {tool_name}", extra={"tool": tool_name, "status": status})


def log_error(msg: str, exc: Exception | None = None):
    get_logger("error").error(msg, exc_info=exc)
