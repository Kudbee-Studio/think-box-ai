"""FIX23: PR #189 audit pass shape."""
from __future__ import annotations
import json
from typing import Any

def apply_fix() -> dict[str, Any]:
    from thinkbox.kilo_pr189_think_job_lifecycle_major_fixes import EXPECTED_FIX_COUNT, PR189_PASS_REL
    from thinkbox.kilo_live_proof_readiness import REPO_ROOT
    body = json.loads((REPO_ROOT / PR189_PASS_REL).read_text(encoding="utf-8"))
    ok = body.get("fix_count") == EXPECTED_FIX_COUNT and body.get("live_verified") is False
    return {"fix_id": "FIX23", "audit_ok": ok, "live_api_called": False}
