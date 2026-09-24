"""FIX06: PR #183 e2e deepen gate."""
from __future__ import annotations
from typing import Any

def apply_fix() -> dict[str, Any]:
    from thinkbox import kilo_pr183_think_job_hermetic_e2e as pr183
    ok, _ = pr183.validate_features_manifest()
    return {"fix_id": "FIX06", "ok": ok, "live_api_called": False}
