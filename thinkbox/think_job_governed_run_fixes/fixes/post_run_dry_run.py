"""FIX11: Post-run dry_run hermetic."""
from __future__ import annotations
from typing import Any

def apply_fix() -> dict[str, Any]:
    from thinkbox.think_job_post_run_deepen.dry_run import dry_run_post_run
    r = dry_run_post_run("x")
    return {"fix_id": "FIX11", "ok": r.get("dry_run") is True, "live_api_called": False}
