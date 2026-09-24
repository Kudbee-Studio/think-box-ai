"""Orchestrate full local PR #185 workflow."""

from __future__ import annotations

from typing import Any

from thinkbox.think_job_lifecycle_fixes.local.bootstrap import ensure_repo_on_path
from thinkbox.think_job_lifecycle_fixes.local.steps_registry import LOCAL_STEPS, run_all_local_steps


def run_local_workflow(dry_run: bool = False) -> dict[str, Any]:
    ensure_repo_on_path()
    if dry_run:
        return {
            "dry_run": True,
            "steps": [fn.__name__ for fn in LOCAL_STEPS],
            "live_api_called": False,
        }
    summary = run_all_local_steps()
    summary["dry_run"] = False
    return summary
