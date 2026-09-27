"""FIX04: w3_webhook_signature_dry_run (PR #192)."""
from __future__ import annotations
from typing import Any

def apply_fix() -> dict[str, Any]:
    from thinkbox.kudbee_sdk_followup_w3.webhook_signature import sign_payload, verify_signature
    sig = sign_payload(b"k", b"{}")
    v = verify_signature(b"k", b"{}", sig, dry_run=True)
    return {"fix_id": "FIX04", "ok": v.valid, "live_api_called": False}
