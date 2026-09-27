"""FIX14: route catalog module."""
from __future__ import annotations
from typing import Any

def apply_fix() -> dict[str, Any]:
    from thinkbox.think_job_post_run_deepen.route_catalog import post_run_routes
    routes = post_run_routes()
    return {"fix_id": "FIX14", "ok": len(routes) >= 1, "live_api_called": False}
