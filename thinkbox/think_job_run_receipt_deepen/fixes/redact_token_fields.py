"""FIX06: Redact export strips token keys."""
from __future__ import annotations
from typing import Any

def apply_fix() -> dict[str, Any]:
    from thinkbox.think_job_run_receipt_deepen.redact_export import redact
    out = redact({"token": "x", "receipt_id": "r"})
    return {"fix_id": "FIX06", "redacted": out["token"] == "[REDACTED]", "live_api_called": False}
