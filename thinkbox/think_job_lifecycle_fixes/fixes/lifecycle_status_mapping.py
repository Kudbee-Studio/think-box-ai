"""FIX01: Map #183 lifecycle states to HTTP status catalog."""
from __future__ import annotations
from typing import Any

_MAP = {
    "RUNNING": "running",
    "COMPLETE": "completed",
    "FAILED": "failed",
    "CONFIGURED": "started",
}

def http_status_for_lifecycle(state: str) -> str | None:
    return _MAP.get(state.upper())

def apply_fix() -> dict[str, Any]:
    from thinkbox.think_job_post_run_deepen.status_catalog import status_catalog
    codes = {row["code"] for row in status_catalog()}
    mapped = {k: v for k, v in _MAP.items() if v in codes}
    return {"fix_id": "FIX01", "mapped": mapped, "ok": len(mapped) >= 3, "live_api_called": False}
