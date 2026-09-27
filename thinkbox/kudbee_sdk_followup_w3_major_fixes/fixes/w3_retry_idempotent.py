"""FIX12: w3_retry_idempotent (PR #192)."""
from __future__ import annotations
from typing import Any

def apply_fix() -> dict[str, Any]:
    from thinkbox.kudbee_sdk_followup_w3.retry import is_idempotent_method
    return {"fix_id": "FIX12", "ok": is_idempotent_method("GET") and not is_idempotent_method("POST"), "live_api_called": False}
