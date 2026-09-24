"""FIX03: w3_dry_run_transport (PR #192)."""
from __future__ import annotations
from typing import Any

def apply_fix() -> dict[str, Any]:
    from thinkbox.kudbee_sdk_followup_w3.clients import KudbeeSdkFollowupW3Client
    h = KudbeeSdkFollowupW3Client.from_env().health()
    return {"fix_id": "FIX03", "ok": h["ready"], "live_api_called": False}
