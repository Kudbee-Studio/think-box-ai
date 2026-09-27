"""Redacted chain export (PR #182 F08)."""

from __future__ import annotations

import re
from typing import Any

_SECRET_PATTERNS = (
    re.compile(r"sk-[A-Za-z0-9]{8,}", re.I),
    re.compile(r"Bearer\s+[A-Za-z0-9._-]+", re.I),
)


def redact_value(value: str) -> str:
    out = value
    for pat in _SECRET_PATTERNS:
        out = pat.sub("[REDACTED]", out)
    return out


def export_chain_redacted(entries: list[dict[str, Any]]) -> dict[str, Any]:
    safe: list[dict[str, Any]] = []
    for row in entries:
        copy = dict(row)
        for key in ("reason", "metadata"):
            val = copy.get(key)
            if isinstance(val, str):
                copy[key] = redact_value(val)
            elif isinstance(val, dict):
                copy[key] = {k: redact_value(str(v)) for k, v in val.items()}
        safe.append(copy)
    return {
        "entries": safe,
        "count": len(safe),
        "redacted": True,
        "live_api_called": False,
    }
