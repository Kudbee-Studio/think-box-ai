"""FIX08: Weak ETag prefix W/."""
from __future__ import annotations
from typing import Any

def apply_fix() -> dict[str, Any]:
    from thinkbox.think_job_run_receipt_deepen.etag_stub import weak_etag
    tag = weak_etag(b"abc")
    return {"fix_id": "FIX08", "ok": tag.startswith('W/"'), "live_api_called": False}
