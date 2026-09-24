"""Redaction helpers for wave LR-energy deepen SDK summaries (PR #193 F04)."""

from __future__ import annotations

from typing import Any

_SENSITIVE_KEYS = frozenset(
    {"token", "secret", "password", "api_key", "authorization", "bearer"},
)


def redact_mapping(doc: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in doc.items():
        if any(part in key.lower() for part in _SENSITIVE_KEYS):
            out[key] = "[REDACTED]"
        else:
            out[key] = value
    return out
