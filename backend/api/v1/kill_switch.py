"""Control plane: kill-switch/quarantine POST + events."""

from datetime import datetime, timezone
from typing import Any, Dict

from fastapi import APIRouter, Header, HTTPException
from fastapi.responses import StreamingResponse
import asyncio

LOCAL_DEV_TOKEN = "dev-only-local-token"

kill_api = APIRouter(prefix="/api/v1/control-plane", tags=["control-plane"])


def _require_dev_auth(authorization: str = Header(None)) -> str:
    if not authorization or authorization != f"Bearer {LOCAL_DEV_TOKEN}":
        raise HTTPException(status_code=401, detail="Unauthorized")
    return authorization


@kill_api.post("/kill-switch")
async def trigger_kill(authorization: str = Header(None), reason: str = "") -> Dict[str, Any]:
    """Trigger kill-switch (fail-closed auth)."""
    _require_dev_auth(authorization)
    return {
        "killed": True,
        "reason": reason or "manual",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "evidence_label": "simulated",
        "_demo": True,
    }


@kill_api.post("/quarantine")
async def toggle_quarantine(
    authorization: str = Header(None),
    agent_id: str = "",
    action: str = "quarantine",  # "quarantine" or "clear"
) -> Dict[str, Any]:
    """Set or clear quarantine flag."""
    _require_dev_auth(authorization)
    return {
        "agent_id": agent_id,
        "quarantined": action == "quarantine",
        "action": action,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "evidence_label": "simulated",
        "_demo": True,
    }


@kill_api.get("/kill-events")
async def kill_events(authorization: str = Header(None)):
    """Event stream for kill/quarantine events."""
    _require_dev_auth(authorization)
    async def stream():
        yield f"data: {{\"events\": [], \"evidence_label\": \"simulated\"}}\n\n"
    return StreamingResponse(stream(), media_type="text/event-stream")
