"""Integration demo for lifecycle fix pack (PR #185)."""

from __future__ import annotations

from typing import Any

from thinkbox.think_job_lifecycle_fixes.negotiation import THINK_JOB_LIFECYCLE_FIXES_VERSION


def integration_summary() -> dict[str, Any]:
    from thinkbox.think_job_lifecycle_fixes.fixes.fix_registry import run_all_fixes

    fixes = run_all_fixes()
    return {
        "version": THINK_JOB_LIFECYCLE_FIXES_VERSION,
        "fix_count": fixes.get("fix_count"),
        "all_hermetic": fixes.get("all_hermetic"),
        "live_verified": False,
        "live_api_called": False,
    }
