"""Think Job status catalog for hermetic e2e (PR #183 F15)."""

from __future__ import annotations

from typing import Any


def status_catalog() -> list[dict[str, str]]:
    return [
        {"code": "PENDING", "terminal": "false"},
        {"code": "CONFIGURED", "terminal": "false"},
        {"code": "RUNNING", "terminal": "false"},
        {"code": "COMPLETE", "terminal": "true"},
        {"code": "FAILED", "terminal": "true"},
        {"code": "CANCELLED", "terminal": "true"},
    ]


def lookup_status(code: str) -> dict[str, Any]:
    for row in status_catalog():
        if row["code"] == code:
            return {"found": True, "status": row, "live_api_called": False}
    return {"found": False, "code": code, "live_api_called": False}
