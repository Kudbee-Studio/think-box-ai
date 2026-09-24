"""EXP19: quantitative_metrics_snapshot expansion pack (PR #192)."""
from __future__ import annotations

from thinkbox.kudbee_sdk_followup_w3_expansion.energy_loop import EnergyLoop
from thinkbox.kudbee_sdk_followup_w3_expansion.long_range import LongRangeLink

def activate_pack() -> dict[str, object]:
    metrics = {
        "link": LongRangeLink.open("m").ping(),
        "energy": EnergyLoop.open("m").snapshot(),
    }
    return {"pack_id": "EXP19", "ok": metrics["energy"]["conserved"], "live_api_called": False}
