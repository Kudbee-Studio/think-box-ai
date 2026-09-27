"""FIX13: w3_observability_reset (PR #192)."""
from __future__ import annotations
from typing import Any

def apply_fix() -> dict[str, Any]:
    from thinkbox.kudbee_sdk_followup_w3.observability import get_metrics, reset_metrics_for_tests
    reset_metrics_for_tests()
    return {"fix_id": "FIX13", "ok": get_metrics().requests == 0, "live_api_called": False}
