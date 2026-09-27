"""KUDBEECLI Phase 2 — read-only dashboard status (in-process state, no live Mercury)."""

from __future__ import annotations

from typing import Any

from thinkbox.cli_inspect import redacted_environment_snapshot
from thinkbox.cli_persist import persist_paths_report
from thinkbox.dashboard_state import get_dashboard_state
from thinkbox.substrate import detect_substrate


def dashboard_status_report(include_env: bool = True) -> dict[str, Any]:
    """Aggregate local dashboard singleton + CLI persistence paths."""
    state = get_dashboard_state().get_state()
    report: dict[str, Any] = {
        "substrate": detect_substrate(),
        "dashboard_summary": state.get("summary", {}),
        "think_boxes": len(state.get("think_boxes", [])),
        "think_jobs": len(state.get("think_jobs", [])),
        "recent_events": len(state.get("events", [])),
        "persist": persist_paths_report(),
        "live_mercury_queried": False,
        "evidence_label": "inferred",
    }
    if include_env:
        env = redacted_environment_snapshot()
        report["environment"] = {
            "substrate": env.get("substrate"),
            "watched_env_count": len(env.get("watched_env", {})),
        }
    return report
