"""HTTP run error codes (hermetic catalog)."""

from __future__ import annotations

from typing import Any


def error_catalog() -> list[dict[str, str]]:
    return [
        {"code": "unauthorized", "http_status": "401"},
        {"code": "validation_error", "http_status": "422"},
        {"code": "admission_denied", "http_status": "403"},
    ]


def lookup_error(code: str) -> dict[str, Any]:
    for row in error_catalog():
        if row["code"] == code:
            return {"found": True, "error": row, "live_api_called": False}
    return {"found": False, "code": code, "live_api_called": False}
