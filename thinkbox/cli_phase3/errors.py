"""Structured KUDBEECLI Phase 3 errors (PR #180 F02)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class CliPhase3Error(Exception):
    """Phase 3 CLI error with stable code."""

    code: str
    message: str
    context: dict[str, Any]

    def __str__(self) -> str:
        return f"{self.code}: {self.message}"


def profile_error(message: str, **context: Any) -> CliPhase3Error:
    return CliPhase3Error(code="CLI_PHASE3_PROFILE", message=message, context=dict(context))


def sandbox_error(message: str, **context: Any) -> CliPhase3Error:
    return CliPhase3Error(code="CLI_PHASE3_SANDBOX", message=message, context=dict(context))


def validation_error(message: str, **context: Any) -> CliPhase3Error:
    return CliPhase3Error(code="CLI_PHASE3_VALIDATION", message=message, context=dict(context))
