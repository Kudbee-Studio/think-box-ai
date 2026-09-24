"""FIX21: API key query stub must not leak in integration summary."""
from __future__ import annotations
from typing import Any

def apply_fix() -> dict[str, Any]:
    from thinkbox.think_job_post_run_deepen.integrate import integration_summary
    summary = integration_summary()
    blob = str(summary)
    return {"fix_id": "FIX21", "no_api_key": "api_key=" not in blob.lower(), "live_api_called": False}
