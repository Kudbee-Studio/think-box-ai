"""FIX25: secret_bearer_scan (PR #192)."""
from __future__ import annotations
from typing import Any

def apply_fix() -> dict[str, Any]:
    from thinkbox.kudbee_sdk_followup_w3.secrets import scan_text_for_secrets
    dirty = scan_text_for_secrets("Bearer sk-abcdefghijklmnopqrstuvwxyz12345")
    return {"fix_id": "FIX25", "ok": not dirty.clean, "live_api_called": False}
