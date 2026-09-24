"""FIX03: Governance bind rejects whitespace token."""
from __future__ import annotations
from typing import Any

def apply_fix() -> dict[str, Any]:
    from thinkbox.think_job_run_receipt_deepen.governance_bind import bind_governance
    return {"fix_id": "FIX03", "ws_denied": not bind_governance("  ")["admitted"], "live_api_called": False}
