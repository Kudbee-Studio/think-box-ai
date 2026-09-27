"""Graceful degradation when remote is absent (PR #179 F21)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, TypeVar

T = TypeVar("T")


@dataclass(frozen=True)
class DegradedValue:
    value: Any
    degraded: bool
    reason: str | None = None


def call_or_degrade(
    fn: Callable[[], T],
    fallback: Callable[[], T],
    *,
    absent_types: tuple[type[BaseException], ...] = (OSError, ConnectionError),
) -> DegradedValue:
    try:
        return DegradedValue(value=fn(), degraded=False)
    except absent_types as exc:
        return DegradedValue(value=fallback(), degraded=True, reason=str(exc))
