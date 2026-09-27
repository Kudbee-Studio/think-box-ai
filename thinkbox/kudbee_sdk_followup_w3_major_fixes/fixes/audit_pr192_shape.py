"""FIX27: audit_pr192_shape (PR #192)."""
from __future__ import annotations
from typing import Any

def apply_fix() -> dict[str, Any]:
    import json
    from thinkbox.kilo_live_proof_readiness import REPO_ROOT
    body = json.loads((REPO_ROOT / "docs/audit/passes/2026-09-24-pr192.json").read_text())
    return {"fix_id": "FIX27", "ok": body["fix_count"] == 35, "live_api_called": False}
