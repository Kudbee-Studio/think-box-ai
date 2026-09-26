"""API endpoints for autonomous decision-loop inspection, tracking, and telemetry."""

from __future__ import annotations

from typing import Any

from thinkbox.autonomous_loop_api_surface import (
    AUTONOMOUS_LOOP_API_VERSION,
    AUTONOMOUS_LOOP_SCHEMA_VERSION,
    get_autonomous_loop_payload,
    get_autonomous_loop_session_payload,
    get_autonomous_loop_session_summary_payload,
    get_autonomous_loop_status_payload,
    get_autonomous_loop_telemetry_payload,
    list_autonomous_loop_sessions_payload,
    list_autonomous_loops_payload,
    list_autonomous_loop_telemetry_payload,
)

try:
    from fastapi import APIRouter, HTTPException, Query

    autonomous_loop_router = APIRouter(prefix="/api/v1/autonomous-loop", tags=["autonomous-loop"])

    @autonomous_loop_router.get("/status")
    async def get_autonomous_loop_status() -> dict[str, Any]:
        """Overview status of all autonomous decision loops."""
        return get_autonomous_loop_status_payload()

    @autonomous_loop_router.get("/loops")
    async def list_autonomous_loops() -> list[dict[str, Any]]:
        """List all registered autonomous loops with components and summary metrics."""
        return list_autonomous_loops_payload()

    @autonomous_loop_router.get("/loops/{loop_id}")
    async def get_autonomous_loop(loop_id: str) -> dict[str, Any]:
        """Retrieve details for a specific autonomous loop."""
        payload = get_autonomous_loop_payload(loop_id)
        if payload is None:
            raise HTTPException(status_code=404, detail=f"Autonomous loop '{loop_id}' not found")
        return payload

    @autonomous_loop_router.get("/telemetry")
    async def list_autonomous_loop_telemetry() -> list[dict[str, Any]]:
        """Get telemetry data for all autonomous loops."""
        return list_autonomous_loop_telemetry_payload()

    @autonomous_loop_router.get("/telemetry/{loop_id}")
    async def get_autonomous_loop_telemetry(loop_id: str) -> dict[str, Any]:
        """Get detailed telemetry for a specific autonomous loop."""
        payload = get_autonomous_loop_telemetry_payload(loop_id)
        if payload is None:
            raise HTTPException(status_code=404, detail=f"Autonomous loop '{loop_id}' not found")
        return payload

    @autonomous_loop_router.get("/sessions")
    async def list_autonomous_loop_sessions(limit: int = Query(default=50, ge=1, le=200)) -> list[dict[str, Any]]:
        """List closed autonomous loop sessions ordered by recency.

        Sessions are complete loop cycles: start -> multiple iterations ->
        feedback -> opportunities -> generalization -> close. Each session
        captures aggregate metrics (throughput, latency, error rate, cycle time)
        for cross-cycle comparison.
        """
        return list_autonomous_loop_sessions_payload(limit=limit)

    @autonomous_loop_router.get("/sessions/{session_id}")
    async def get_autonomous_loop_session(session_id: str) -> dict[str, Any]:
        """Retrieve details for a specific closed loop session."""
        payload = get_autonomous_loop_session_payload(session_id)
        if payload is None:
            raise HTTPException(status_code=404, detail=f"Autonomous loop session '{session_id}' not found")
        return payload

    @autonomous_loop_router.get("/sessions/summary")
    async def get_autonomous_loop_session_summary() -> dict[str, Any]:
        """Lightweight summary of all closed sessions for status polling."""
        return get_autonomous_loop_session_summary_payload()

    @autonomous_loop_router.post("/loops/{loop_id}/actions/{action}")
    async def post_loop_action(loop_id: str, action: str, payload: dict[str, Any] = {}, authorization: str | None = None, x_governance_token: str | None = None) -> dict[str, Any]:
        """Record an action (start/stop/run/reset) on a loop.
        Returns the created LoopActionEntry payload.
        Requires a governance token for side‑effect protection.
        """
        allowed = {"start", "stop", "run", "reset"}
        if action not in allowed:
            raise HTTPException(status_code=400, detail=f"Invalid action '{action}'. Allowed: {allowed}")
        # Extract governance token similar to other protected endpoints
        token = x_governance_token.strip() if x_governance_token else (authorization[7:].strip() if authorization and authorization.lower().startswith("bearer ") else "")
        if not token:
            raise HTTPException(status_code=401, detail="Missing governance token")
        # NOTE: token validation is handled by AdmissionGate elsewhere; we enforce presence here.
        state = get_dashboard_state()
        entry = state.record_loop_action(loop_id, action, result=payload)
        return entry.model_dump()

    @autonomous_loop_router.get("/loops/{loop_id}/actions")
    async def get_loop_actions(loop_id: str) -> list[dict[str, Any]]:
        """Retrieve recorded actions for a specific loop."""
        state = get_dashboard_state()
        actions = state.get_loop_actions(loop_id)
        return [a.model_dump() for a in actions]

    @autonomous_loop_router.get("/actions")
    async def list_all_actions() -> list[dict[str, Any]]:
        """List all loop actions across all loops."""
        state = get_dashboard_state()
        actions = state.get_all_loop_actions()
        return [a.model_dump() for a in actions]

    @autonomous_loop_router.get("/sessions/summary")
    async def get_autonomous_loop_session_summary() -> dict[str, Any]:
        """Lightweight summary of all closed sessions for status polling."""
        return get_autonomous_loop_session_summary_payload()

except ImportError:
    # Fail-closed / headless fallback when FastAPI is not installed in runtime environment
    autonomous_loop_router = None  # type: ignore[assignment]
