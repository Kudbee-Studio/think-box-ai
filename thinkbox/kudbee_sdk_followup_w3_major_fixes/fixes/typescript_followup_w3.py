"""FIX23: typescript_followup_w3 (PR #192)."""
from __future__ import annotations
from typing import Any

def apply_fix() -> dict[str, Any]:
    from thinkbox.kilo_live_proof_readiness import REPO_ROOT
    path = REPO_ROOT / "apps/web/sdk/followup_w3.ts"
    text = path.read_text(encoding="utf-8")
    return {"fix_id": "FIX23", "ok": "SDK_FOLLOWUP_W3_VERSION" in text, "live_api_called": False}
