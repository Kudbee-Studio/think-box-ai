"""FIX24: Audit pass documents fix_count 25 and honesty flags."""
from __future__ import annotations
import json
from typing import Any

def apply_fix() -> dict[str, Any]:
    from thinkbox.kilo_pr185_think_job_lifecycle_fixes import PR185_PASS_REL, EXPECTED_FIX_COUNT
    from thinkbox.kilo_live_proof_readiness import REPO_ROOT
    path = REPO_ROOT / PR185_PASS_REL
    body = json.loads(path.read_text(encoding="utf-8"))
    ok = (
        body.get("fix_count") == EXPECTED_FIX_COUNT
        and body.get("live_verified") is False
        and body.get("combined_umbrella_nested") is False
    )
    return {"fix_id": "FIX24", "audit_ok": ok, "live_api_called": False}
