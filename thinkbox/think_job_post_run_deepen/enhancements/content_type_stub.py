"""Content-Type guard for JSON POST /run."""

from __future__ import annotations

from typing import Any


def json_content_type_ok(content_type: str | None) -> dict[str, Any]:
    ct = (content_type or "").split(";")[0].strip().lower()
    return {
        "ok": ct in ("application/json", "application/json; charset=utf-8", ""),
        "content_type": ct or "missing",
        "live_api_called": False,
    }
