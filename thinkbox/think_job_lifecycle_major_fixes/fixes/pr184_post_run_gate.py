"""FIX07: PR #184 post-run deepen gate."""
from __future__ import annotations
from typing import Any

def apply_fix() -> dict[str, Any]:
    from thinkbox import kilo_pr184_think_job_post_run_deepen as pr184
    ok, _ = pr184.validate_features_manifest()
    return {"fix_id": "FIX07", "ok": ok, "live_api_called": False}
