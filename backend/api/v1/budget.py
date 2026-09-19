"""Control plane status endpoint: budget breaker status + trip event stream."""

import asyncio
from datetime import datetime, timezone
from typing import Any, Dict, List

from fastapi import APIRouter, Header, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import StreamingResponse

from thinkbox.dashboard_state import get_dashboard_state, DashboardCategory, DashboardEvent, DashboardEventEntry

LOCAL_DEV_TOKEN = "dev-only-local-token"

budget_api = APIRouter(prefix="/api/v1/control-plane", tags=["control-plane"])
_dashboard_state = get_dashboard_state()


def _require_dev_auth(authorization: str = Header(None)) -> str:
    if not authorization or authorization != f"Bearer {LOCAL_DEV_TOKEN}":
        raise HTTPException(status_code=401, detail="Unauthorized")
    return authorization


@budget_api.get("/budget")
async def budget_status(authorization: str = Header(None)) -> Dict[str, Any]:
    """Budget breaker status."""
    _require_dev_auth(authorization)
    return {
        "spent": 0.0,
        "limit": 100.0,
        "currency": "usd",
        "remaining": 100.0,
        "tripped": False,
        "reason_code": "",
        "evidence_label": "simulated",
        "_demo": True,
    }


@budget_api.get("/budget/trip-events")
async def budget_trip_stream(authorization: str = Header(None)):
    """Server-sent events for budget trip events."""
    _require_dev_auth(authorization)
    async def stream():
        queue = asyncio.Queue()
        await _dashboard_state.register_subscriber(queue)
        try:
            while True:
                event = await queue.get()
                yield f"data: {event.model_dump()}\n\n"
        except asyncio.CancelledError:
            _dashboard_state._subscribers.remove(queue)
            raise

    return StreamingResponse(stream(), media_type="text/event-stream")
