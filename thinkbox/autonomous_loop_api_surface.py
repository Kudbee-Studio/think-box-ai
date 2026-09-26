"""Core service logic and contract helpers for Autonomous Loop Control Plane API."""

from __future__ import annotations

from typing import Any

from thinkbox.dashboard_state import (
    AutonomousLoopEntry,
    AutonomousLoopTelemetry,
    DashboardState,
    get_dashboard_state,
)

AUTONOMOUS_LOOP_API_VERSION = "autonomous-loop-api-v1"
AUTONOMOUS_LOOP_SCHEMA_VERSION = "1.0.0"


def get_autonomous_loop_status_payload(state: DashboardState | None = None) -> dict[str, Any]:
    """Build status summary payload for autonomous loops."""
    if state is None:
        state = get_dashboard_state()
    loops = [entry.model_dump() for entry in state.autonomous_loops.values()]
    total = len(loops)
    active = sum(1 for loop in loops if loop.get("status") in {"running", "active"})
    bootstrapped = sum(1 for loop in loops if loop.get("bootstrapped", False))

    summary = state.get_state_summary()
    telemetry_summary = summary.get("loop_telemetry_summary", {})

    return {
        "status": "healthy" if total > 0 else "idle",
        "total_loops": total,
        "active_loops": active,
        "bootstrapped_loops": bootstrapped,
        "revision": state.revision(),
        "api_version": AUTONOMOUS_LOOP_API_VERSION,
        "schema_version": AUTONOMOUS_LOOP_SCHEMA_VERSION,
        "telemetry_summary": telemetry_summary,
    }


def list_autonomous_loops_payload(state: DashboardState | None = None) -> list[dict[str, Any]]:
    """List all registered autonomous loops."""
    if state is None:
        state = get_dashboard_state()
    return [entry.model_dump() for entry in state.autonomous_loops.values()]


def get_autonomous_loop_payload(loop_id: str, state: DashboardState | None = None) -> dict[str, Any] | None:
    """Retrieve payload for a specific loop or None if not found."""
    if state is None:
        state = get_dashboard_state()
    entry = state.autonomous_loops.get(loop_id)
    if entry is None:
        return None
    return entry.model_dump()


def list_autonomous_loop_telemetry_payload(state: DashboardState | None = None) -> list[dict[str, Any]]:
    """Get all loops telemetry list."""
    if state is None:
        state = get_dashboard_state()
    return state.get_all_loop_telemetry()


def get_autonomous_loop_telemetry_payload(loop_id: str, state: DashboardState | None = None) -> dict[str, Any] | None:
    """Get telemetry for a specific loop; returns None if loop doesn't exist."""
    if state is None:
        state = get_dashboard_state()
    if loop_id not in state.autonomous_loops:
        return None
    telemetry = state.get_loop_telemetry(loop_id)
    if telemetry is None:
        return AutonomousLoopTelemetry().model_dump()
    return telemetry.model_dump()
