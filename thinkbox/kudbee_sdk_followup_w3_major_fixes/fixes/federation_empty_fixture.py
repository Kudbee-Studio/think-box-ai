"""FIX30: federation_empty_fixture (PR #192)."""
from __future__ import annotations
from typing import Any

def apply_fix() -> dict[str, Any]:
    import json
    from thinkbox.kilo_live_proof_readiness import REPO_ROOT
    path = REPO_ROOT / "data/kudbee_sdk/fixtures/w3/twin_federation_empty.json"
    doc = json.loads(path.read_text())
    return {"fix_id": "FIX30", "ok": doc.get("peer_count") == 0, "live_api_called": False}
