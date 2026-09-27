"""Redacted export (PR #186 F09)."""
from __future__ import annotations
from typing import Any

def redact(payload: dict[str, Any]) -> dict[str, Any]:
    out = dict(payload)
    for key in ("token", "authorization", "api_key"):
        if key in out:
            out[key] = "[REDACTED]"
    return out
