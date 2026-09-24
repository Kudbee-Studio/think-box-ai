"""FIX10: Cassette replay has receipt steps."""
from __future__ import annotations
from typing import Any

def apply_fix() -> dict[str, Any]:
    from thinkbox.think_job_run_receipt_deepen.cassette import replay_cassette
    tape = replay_cassette("receipt_deepen_flow.json")
    return {"fix_id": "FIX10", "steps": tape["step_count"] >= 2, "live_api_called": False}
