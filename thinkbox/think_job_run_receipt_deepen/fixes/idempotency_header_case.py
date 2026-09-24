"""FIX07: Idempotency header case insensitive."""
from __future__ import annotations
from typing import Any

def apply_fix() -> dict[str, Any]:
    from thinkbox.think_job_run_receipt_deepen.idempotency_bind import idempotency_key
    return {"fix_id": "FIX07", "ok": idempotency_key({"idempotency-key": "k"}) == "k", "live_api_called": False}
