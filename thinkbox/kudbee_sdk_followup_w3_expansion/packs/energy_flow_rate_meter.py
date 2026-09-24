"""EXP11: energy_flow_rate_meter expansion pack (PR #192)."""
from __future__ import annotations

from thinkbox.kudbee_sdk_followup_w3_expansion.energy_loop import EnergyLoop

def activate_pack() -> dict[str, object]:
    loop = EnergyLoop.open("e-3")
    loop.deposit(1.0)
    loop.deposit(3.0)
    return {"pack_id": "EXP11", "ok": loop.free_flow_rate() == 2.0, "live_api_called": False}
