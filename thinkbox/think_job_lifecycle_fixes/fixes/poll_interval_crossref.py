"""FIX15: Cross-reference poll interval guard with status poll stub."""
from __future__ import annotations
from typing import Any

def apply_fix() -> dict[str, Any]:
    from thinkbox.think_job_e2e_deepen.fixes.poll_interval_guard import clamp_poll_interval
    from thinkbox.think_job_post_run_deepen.status_poll_stub import status_poll_hint
    hint = status_poll_hint()
    clamped = clamp_poll_interval(hint.get("interval_s", 0.0))
    return {"fix_id": "FIX15", "clamped": clamped >= hint.get("min_interval_s", 0.0), "live_api_called": False}
