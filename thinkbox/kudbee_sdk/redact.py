"""Redact secrets from config and log payloads (PR #177 F04)."""

from __future__ import annotations

import re
from typing import Any

_REDACT_KEYS = frozenset(
    {
        "token",
        "api_key",
        "apikey",
        "password",
        "secret",
        "authorization",
        "bearer",
        "upstash_public_box_token",
        "thinkbox_upcloud_api_token",
    },
)

_BEARER_RE = re.compile(r"Bearer\s+[A-Za-z0-9._\-]+", re.IGNORECASE)
_SK_RE = re.compile(r"sk-[A-Za-z0-9]{8,}", re.IGNORECASE)


def redact_string(value: str) -> str:
    out = _BEARER_RE.sub("Bearer [REDACTED]", value)
    return _SK_RE.sub("sk-[REDACTED]", out)


def redact_mapping(data: dict[str, Any]) -> dict[str, Any]:
    redacted: dict[str, Any] = {}
    for key, val in data.items():
        key_l = key.lower()
        if any(part in key_l for part in _REDACT_KEYS):
            redacted[key] = "[REDACTED]"
        elif isinstance(val, dict):
            redacted[key] = redact_mapping(val)
        elif isinstance(val, str):
            redacted[key] = redact_string(val)
        else:
            redacted[key] = val
    return redacted
