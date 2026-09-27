"""FIX02: Ensure started is in deepen status catalogs."""
from __future__ import annotations
from typing import Any

def apply_fix() -> dict[str, Any]:
    from thinkbox.think_job_post_run_deepen.status_catalog import status_catalog
    codes = [r["code"] for r in status_catalog()]
    return {"fix_id": "FIX02", "has_started": "started" in codes, "codes": codes, "live_api_called": False}
