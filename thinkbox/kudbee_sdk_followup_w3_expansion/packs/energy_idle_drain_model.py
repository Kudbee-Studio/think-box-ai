"""EXP13: energy_idle_drain_model expansion pack (PR #192)."""
from __future__ import annotations

from thinkbox.kudbee_sdk_followup_w3_expansion.energy_loop import EnergyLoop

def activate_pack() -> dict[str, object]:
    loop = EnergyLoop.open("e-5")
    snap = loop.snapshot()
    return {"pack_id": "EXP13", "ok": snap["free_flow_rate"] == 0.0, "live_api_called": False}
