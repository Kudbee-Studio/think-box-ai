"""EXP09: energy_loop_open expansion pack (PR #192)."""
from __future__ import annotations

from thinkbox.kudbee_sdk_followup_w3_expansion.energy_loop import EnergyLoop

def activate_pack() -> dict[str, object]:
    loop = EnergyLoop.open("e-1")
    return {"pack_id": "EXP09", "ok": loop.conserved(), "live_api_called": False}
