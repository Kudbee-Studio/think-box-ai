"""FIX02: w3_config_fail_closed (PR #192)."""
from __future__ import annotations
from typing import Any

def apply_fix() -> dict[str, Any]:
    from thinkbox.kudbee_sdk_followup_w3.config import load_config_from_env
    cfg = load_config_from_env({"KUDBEE_SDK_FOLLOWUP_W3_DRY_RUN": "true"})
    return {"fix_id": "FIX02", "ok": cfg.dry_run, "live_api_called": False}
