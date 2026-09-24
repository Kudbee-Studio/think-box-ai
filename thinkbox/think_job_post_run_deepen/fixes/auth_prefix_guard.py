from __future__ import annotations
from typing import Any
from thinkbox.think_job_post_run_deepen.auth_stub import auth_ok
def apply_fix() -> dict[str, Any]:
    return {"fix_id": "FIX03", **auth_ok("tb_ok"), "live_api_called": False}
