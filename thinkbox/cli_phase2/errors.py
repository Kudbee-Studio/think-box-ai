"""Structured KUDBEECLI Phase 2 errors with stable codes (PR #178 F02)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class CliToolkitError(Exception):
    """Base SDK error with a stable machine-readable code."""

    code: str
    message: str
    context: dict[str, Any]

    def __str__(self) -> str:
        return f"{self.code}: {self.message}"


def config_error(message: str, **context: Any) -> CliToolkitError:
    return CliToolkitError(code="CLI_TOOLKIT_CONFIG", message=message, context=dict(context))


def transport_error(message: str, **context: Any) -> CliToolkitError:
    return CliToolkitError(code="CLI_TOOLKIT_TRANSPORT", message=message, context=dict(context))


def validation_error(message: str, **context: Any) -> CliToolkitError:
    return CliToolkitError(code="CLI_TOOLKIT_VALIDATION", message=message, context=dict(context))


def remote_absent_error(message: str, **context: Any) -> CliToolkitError:
    return CliToolkitError(code="CLI_TOOLKIT_REMOTE_ABSENT", message=message, context=dict(context))
