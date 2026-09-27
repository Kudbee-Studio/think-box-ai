"""EXP14: energy_throughput_stub expansion pack (PR #192)."""
from __future__ import annotations

from thinkbox.kudbee_sdk_followup_w3_expansion.energy_loop import EnergyLoop

def activate_pack() -> dict[str, object]:
    loop = EnergyLoop.open("e-6")
    loop.deposit(10.0)
    return {"pack_id": "EXP14", "ok": loop.snapshot()["flow_units"] == 10.0, "live_api_called": False}
