"""EXP10: energy_loop_quantize_unit expansion pack (PR #192)."""
from __future__ import annotations

from thinkbox.kudbee_sdk_followup_w3_expansion.energy_loop import EnergyLoop

def activate_pack() -> dict[str, object]:
    loop = EnergyLoop.open("e-2", capacity_units=10.0)
    loop.deposit(2.5)
    return {"pack_id": "EXP10", "ok": loop.flow_units == 2.5, "live_api_called": False}
