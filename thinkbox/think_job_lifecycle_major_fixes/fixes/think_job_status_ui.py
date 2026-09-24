"""FIX13: Think Job status UI module."""
from __future__ import annotations
from typing import Any
from thinkbox.kilo_live_proof_readiness import REPO_ROOT

def apply_fix() -> dict[str, Any]:
    ok = (REPO_ROOT / "thinkbox/think_job_status_ui.py").is_file()
    return {"fix_id": "FIX13", "ok": ok, "live_api_called": False}
