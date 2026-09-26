"""API endpoints for autonomous decision-loop inspection, tracking, and telemetry."""

from __future__ import annotations

from typing import Any

from thinkbox.autonomous_loop_api_surface import (
    get_autonomous_loop_payload,
    get_autonomous_loop_status_payload,
    get_autonomous_loop_telemetry_payload,
    list_autonomous_loop_telemetry_payload,
    list_autonomous_loops_payload,
)

try:
    from fastapi import APIRouter, HTTPException

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

except ImportError:
    # Fail-closed / headless fallback when FastAPI is not installed in runtime environment
    autonomous_loop_router = None  # type: ignore[assignment]
