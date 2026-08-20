"""Logging configuration for THINK BOX AI.

Never logs secrets, tokens, or PII.
"""

from __future__ import annotations

import logging
import sys


def setup_logging(level: str = "INFO") -> logging.Logger:
    """Configure and return the root logger for the application."""
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
