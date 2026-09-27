"""Structured Kudbee SDK follow-up wave LR-energy deepen errors (PR #193 F02)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class SdkLrEnergyError(Exception):
    """Base wave-3 SDK error with a stable machine-readable code."""

    code: str
    message: str
    context: dict[str, Any]

    def __str__(self) -> str:
        return f"{self.code}: {self.message}"


def config_error(message: str, **context: Any) -> SdkLrEnergyError:
    return SdkLrEnergyError(code="SDK_LR_CONFIG", message=message, context=dict(context))


def transport_error(message: str, **context: Any) -> SdkLrEnergyError:
    return SdkLrEnergyError(code="SDK_LR_TRANSPORT", message=message, context=dict(context))


def validation_error(message: str, **context: Any) -> SdkLrEnergyError:
    return SdkLrEnergyError(code="SDK_LR_VALIDATION", message=message, context=dict(context))


def webhook_error(message: str, **context: Any) -> SdkLrEnergyError:
    return SdkLrEnergyError(code="SDK_LR_WEBHOOK", message=message, context=dict(context))
