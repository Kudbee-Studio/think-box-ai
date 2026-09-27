"""FIX05: Validate #183 manifest gate_id and pr_number."""
from __future__ import annotations
from typing import Any

def apply_fix() -> dict[str, Any]:
    from thinkbox import kilo_pr183_think_job_hermetic_e2e as pr183
    doc = pr183.load_features_manifest()
    ok = doc.get("gate_id") == pr183.GATE_ID and doc.get("pr_number") == pr183.PR_NUMBER
    return {"fix_id": "FIX05", "pairing_ok": ok, "live_api_called": False}
