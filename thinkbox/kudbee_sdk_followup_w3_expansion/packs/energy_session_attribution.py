"""EXP17: energy_session_attribution expansion pack (PR #192)."""
from __future__ import annotations

from thinkbox.kudbee_sdk_followup_w3_expansion.energy_loop import EnergyLoop
from thinkbox.kudbee_sdk_followup_w3.session_bridge import SessionBridgeW3

def activate_pack() -> dict[str, object]:
    session = SessionBridgeW3.open("sess-energy")
    loop = EnergyLoop.open(f"loop-{session.session.session_id}")
    loop.deposit(1.0)
    return {"pack_id": "EXP17", "ok": loop.loop_id.endswith("sess-energy"), "live_api_called": False}
