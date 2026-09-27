"""FIX09: w3_cassette_replay (PR #192)."""
from __future__ import annotations
from typing import Any

def apply_fix() -> dict[str, Any]:
    from thinkbox.kudbee_sdk_followup_w3.cassette import replay_cassette
    r = replay_cassette("webhook_flow.json")
    return {"fix_id": "FIX09", "ok": r["step_count"] >= 1, "live_api_called": False}
