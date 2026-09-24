"""Structured KUDBEECLI Phase 4 errors (PR #196 F02)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class CliPhase4Error(Exception):
    """Phase 4 CLI error with stable code."""

    code: str
    message: str
    context: dict[str, Any]

    def __str__(self) -> str:
        return f"{self.code}: {self.message}"


def profile_error(message: str, **context: Any) -> CliPhase4Error:
    return CliPhase4Error(code="CLI_PHASE4_PROFILE", message=message, context=dict(context))


def sandbox_error(message: str, **context: Any) -> CliPhase4Error:
    return CliPhase4Error(code="CLI_PHASE4_SANDBOX", message=message, context=dict(context))


def validation_error(message: str, **context: Any) -> CliPhase4Error:
    return CliPhase4Error(code="CLI_PHASE4_VALIDATION", message=message, context=dict(context))
