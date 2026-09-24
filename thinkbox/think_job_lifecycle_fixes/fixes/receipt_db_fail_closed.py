"""FIX14: Fail-closed when experiment DB path unset."""
from __future__ import annotations
from typing import Any

def apply_fix() -> dict[str, Any]:
    from thinkbox.think_job_lifecycle_fixes.config import experiment_db_configured
    configured = experiment_db_configured()
    return {"fix_id": "FIX14", "configured": configured, "fail_closed": not configured, "live_api_called": False}
