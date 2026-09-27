"""Structured Kudbee SDK follow-up wave 3 errors (PR #191 F02)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class SdkFollowupW3Error(Exception):
    """Base wave-3 SDK error with a stable machine-readable code."""

    code: str
    message: str
    context: dict[str, Any]

    def __str__(self) -> str:
        return f"{self.code}: {self.message}"


def config_error(message: str, **context: Any) -> SdkFollowupW3Error:
    return SdkFollowupW3Error(code="SDK_W3_CONFIG", message=message, context=dict(context))


def transport_error(message: str, **context: Any) -> SdkFollowupW3Error:
    return SdkFollowupW3Error(code="SDK_W3_TRANSPORT", message=message, context=dict(context))


def validation_error(message: str, **context: Any) -> SdkFollowupW3Error:
    return SdkFollowupW3Error(code="SDK_W3_VALIDATION", message=message, context=dict(context))


def webhook_error(message: str, **context: Any) -> SdkFollowupW3Error:
    return SdkFollowupW3Error(code="SDK_W3_WEBHOOK", message=message, context=dict(context))
