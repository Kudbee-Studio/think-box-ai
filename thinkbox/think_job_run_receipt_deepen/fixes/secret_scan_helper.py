"""FIX19: Secret scan detects Bearer."""
from __future__ import annotations
from typing import Any

def apply_fix() -> dict[str, Any]:
    from thinkbox.think_job_run_receipt_deepen.secrets import looks_like_secret
    return {"fix_id": "FIX19", "ok": looks_like_secret("Bearer x"), "live_api_called": False}
