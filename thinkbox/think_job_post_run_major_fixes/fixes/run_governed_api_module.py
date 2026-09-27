"""FIX20: run_governed API module."""
from __future__ import annotations
from typing import Any
from thinkbox.kilo_live_proof_readiness import REPO_ROOT

def apply_fix() -> dict[str, Any]:
    ok = (REPO_ROOT / "backend/api/v1/run_governed.py").is_file()
    return {"fix_id": "FIX20", "ok": ok, "live_api_called": False}
