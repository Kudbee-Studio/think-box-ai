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

except ImportError:
    # Fail-closed / headless fallback when FastAPI is not installed in runtime environment
    autonomous_loop_router = None  # type: ignore[assignment]
