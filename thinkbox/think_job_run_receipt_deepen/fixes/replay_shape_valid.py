"""FIX11: Replay validates receipt shape."""
from __future__ import annotations
from typing import Any

def apply_fix() -> dict[str, Any]:
    from thinkbox.think_job_run_receipt_deepen.replay import replay_steps
    steps = [{"receipt": {"receipt_id": "r", "session_id": "s", "experiment_id": "e"}}]
    return {"fix_id": "FIX11", "valid": replay_steps(steps)["valid"], "live_api_called": False}
