"""Redact Think Job export payloads (PR #183 F08)."""

from __future__ import annotations

import re
from typing import Any, Mapping

_BEARER = re.compile(r"Bearer\s+\S+", re.IGNORECASE)
_TOKEN = re.compile(r"(sk-[a-zA-Z0-9]{8,})")


def redact_value(value: str) -> str:
    out = _BEARER.sub("Bearer [REDACTED]", value)
    return _TOKEN.sub("[REDACTED_TOKEN]", out)


def export_jobs_redacted(rows: list[Mapping[str, Any]]) -> dict[str, Any]:
    cleaned: list[dict[str, Any]] = []
    for row in rows:
        item = dict(row)
        for key in ("reason", "message", "error"):
            if key in item and isinstance(item[key], str):
                item[key] = redact_value(item[key])
        cleaned.append(item)
    return {"jobs": cleaned, "redacted": True, "live_api_called": False}
