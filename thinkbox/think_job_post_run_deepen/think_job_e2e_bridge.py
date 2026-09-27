"""Bridge to PR #183 think_job_e2e_deepen (PR #184 F24)."""
from __future__ import annotations
from typing import Any

def bridge_summary() -> dict[str, Any]:
    from thinkbox.think_job_e2e_deepen.negotiation import THINK_JOB_E2E_DEEPEN_VERSION
    return {
        "think_job_e2e_deepen_version": THINK_JOB_E2E_DEEPEN_VERSION,
        "paired_pr": 183,
        "live_api_called": False,
    }
