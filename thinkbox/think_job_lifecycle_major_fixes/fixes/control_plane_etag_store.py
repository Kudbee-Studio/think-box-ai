"""FIX14: Shared ETag store static asset."""
from __future__ import annotations
from typing import Any
from thinkbox.kilo_live_proof_readiness import REPO_ROOT

def apply_fix() -> dict[str, Any]:
    ok = (REPO_ROOT / "public/control-plane/control_plane_etag_store.js").is_file()
    return {"fix_id": "FIX14", "ok": ok, "live_api_called": False}
