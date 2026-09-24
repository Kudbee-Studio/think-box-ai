"""FIX23: Lazy spine hook for PR #185 verify (no import cycle with #184)."""
from __future__ import annotations
from typing import Any

def spine_summary_lazy() -> dict[str, Any]:
    from thinkbox.kilo_pr185_think_job_lifecycle_fixes import think_job_lifecycle_fixes_contract_summary
    return think_job_lifecycle_fixes_contract_summary()

def apply_fix() -> dict[str, Any]:
    summary = spine_summary_lazy()
    return {
        "fix_id": "FIX23",
        "hermetic_operator_ok": summary.get("hermetic_operator_ok") is True,
        "live_api_called": False,
    }
