"""FIX01: pr191_gate_lazy (PR #192)."""
from __future__ import annotations
from typing import Any

def apply_fix() -> dict[str, Any]:
    from thinkbox.kilo_pr191_kudbee_sdk_followup_w3 import GATE_ID, validate_features_manifest
    ok, _ = validate_features_manifest()
    return {"fix_id": "FIX01", "ok": ok and GATE_ID == "kudbee-sdk-followup-w3", "live_api_called": False}
