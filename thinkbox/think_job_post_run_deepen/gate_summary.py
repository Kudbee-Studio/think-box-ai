"""Gate summary bridge (PR #184 F14 catalog)."""
from __future__ import annotations
from typing import Any

def gate_summary() -> dict[str, Any]:
    from thinkbox.kilo_pr184_think_job_post_run_deepen import (  # lazy: avoid import cycle
        GATE_ID,
        PR_NUMBER,
        think_job_post_run_deepen_contract_summary,
    )
    s = think_job_post_run_deepen_contract_summary()
    return {
        "gate_id": GATE_ID,
        "pr_number": PR_NUMBER,
        "hermetic_operator_ok": s.get("hermetic_operator_ok"),
        "live_verified": False,
        "live_api_called": False,
    }
