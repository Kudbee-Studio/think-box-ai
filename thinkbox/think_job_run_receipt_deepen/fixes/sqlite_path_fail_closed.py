"""FIX04: SQLite path must be non-empty string."""
from __future__ import annotations
from typing import Any

def apply_fix() -> dict[str, Any]:
    from thinkbox.think_job_run_receipt_deepen.sqlite_path_stub import resolve_db
    path = resolve_db()["path"]
    return {"fix_id": "FIX04", "ok": bool(path.strip()), "live_api_called": False}
