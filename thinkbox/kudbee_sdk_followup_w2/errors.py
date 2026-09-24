"""Structured Kudbee SDK follow-up wave 2 errors (PR #181 F02)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class SdkFollowupW2Error(Exception):
    """Base wave-2 SDK error with a stable machine-readable code."""

    code: str
    message: str
    context: dict[str, Any]

    def __str__(self) -> str:
        return f"{self.code}: {self.message}"


def config_error(message: str, **context: Any) -> SdkFollowupW2Error:
    return SdkFollowupW2Error(code="SDK_W2_CONFIG", message=message, context=dict(context))


def transport_error(message: str, **context: Any) -> SdkFollowupW2Error:
    return SdkFollowupW2Error(code="SDK_W2_TRANSPORT", message=message, context=dict(context))


def validation_error(message: str, **context: Any) -> SdkFollowupW2Error:
    return SdkFollowupW2Error(code="SDK_W2_VALIDATION", message=message, context=dict(context))


def webhook_error(message: str, **context: Any) -> SdkFollowupW2Error:
    return SdkFollowupW2Error(code="SDK_W2_WEBHOOK", message=message, context=dict(context))
