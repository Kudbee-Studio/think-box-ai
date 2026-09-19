"""Control plane: lease map API (multi-agent lease status)."""

from datetime import datetime, timezone
from typing import Any, Dict, List

from fastapi import APIRouter, Header, HTTPException

LOCAL_DEV_TOKEN = "dev-only-local-token"

lease_api = APIRouter(prefix="/api/v1/control-plane", tags=["control-plane"])


def _require_dev_auth(authorization: str = Header(None)) -> str:
    if not authorization or authorization != f"Bearer {LOCAL_DEV_TOKEN}":
        raise HTTPException(status_code=401, detail="Unauthorized")
    return authorization


@lease_api.get("/leases")
async def lease_map(authorization: str = Header(None)) -> Dict[str, Any]:
    """Multi-agent lease map: holders, heartbeats, stale leases."""
    _require_dev_auth(authorization)
    return {
        "agents": [
            {
                "agent_id": "agent-1",
                "leases": [
                    {"task_id": "task-1", "acquired": "2026-09-19T20:00:00Z", "ttl_seconds": 300, "leader": False},
                ],
                "last_heartbeat": datetime.now(timezone.utc).isoformat(),
                "healthy": True,
            },
            {
                "agent_id": "agent-2",
                "leases": [],
                "last_heartbeat": "2026-09-19T20:10:00Z",
                "healthy": True,
            },
        ],
        "stale_count": 0,
        "total_leases": 1,
        "evidence_label": "simulated",
        "_demo": True,
    }


@lease_api.get("/leases/{agent_id}")
async def agent_lease(agent_id: str, authorization: str = Header(None)) -> Dict[str, Any]:
    """Single agent lease details."""
    _require_dev_auth(authorization)
    return {
        "agent_id": agent_id,
        "leases": [],
        "is_leader": False,
        "last_heartbeat": datetime.now(timezone.utc).isoformat(),
        "stale": False,
        "evidence_label": "simulated",
        "_demo": True,
    }
