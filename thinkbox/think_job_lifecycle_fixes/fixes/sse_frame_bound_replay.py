"""FIX19: SSE frame bound on post-run replay path."""
from __future__ import annotations
from typing import Any

def apply_fix() -> dict[str, Any]:
    from thinkbox.think_job_e2e_deepen.fixes.sse_frame_bounds import apply_fix as e2e_fix
    from thinkbox.think_job_post_run_deepen.replay import replay_bounds
    e2e = e2e_fix()
    bounds = replay_bounds()
    return {
        "fix_id": "FIX19",
        "within_bounds": bounds["max_bytes"] <= e2e["max_frame_bytes"],
        "live_api_called": False,
    }
