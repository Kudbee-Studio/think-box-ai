"""Pair with PR #185 lifecycle fixes (PR #186 F22)."""
from __future__ import annotations

def pairing_ok() -> bool:
    from thinkbox import kilo_pr185_think_job_lifecycle_fixes as pr185
    return pr185.GATE_ID == "think-job-lifecycle-fixes" and pr185.PR_NUMBER == 185
