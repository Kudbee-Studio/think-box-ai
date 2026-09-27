"""Minimal CI/test environ fixtures (PR #200)."""

from __future__ import annotations


def minimal_hermetic_environ() -> dict[str, str]:
    """Environ safe for unit tests and CI gates (no secrets)."""
    return {
        "CI": "true",
        "THINKBOX_KILO_HERMETIC_MODE": "true",
        "THINKBOX_CLOUD_EXEC_HERMETIC": "true",
        "THINKBOX_LOG_LEVEL": "WARNING",
    }


def minimal_dev_environ() -> dict[str, str]:
    return {
        "THINKBOX_KILO_HERMETIC_MODE": "false",
        "THINKBOX_LOG_LEVEL": "INFO",
        "THINKBOX_DEFAULT_PROVIDER": "openai_compat",
    }
