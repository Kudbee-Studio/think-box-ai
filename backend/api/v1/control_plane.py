"""Control plane status endpoint: admission, capacity, kill-switch, budget."""

from datetime import datetime, timezone
from typing import Any, Dict

from fastapi import APIRouter, Header, HTTPException

from thinkbox.dashboard_state import get_dashboard_state, DashboardCategory, DashboardEvent

logger = __import__("logging").getLogger(__name__)

# Local-dev auth token for testing (NOT for production)
LOCAL_DEV_TOKEN = "dev-only-local-token"

control_plane_api = APIRouter(prefix="/api/v1/control-plane", tags=["control-plane"])


def _require_dev_auth(authorization: str = Header(None)) -> str:
    """Fail-closed: require local-dev token header."""
    if not authorization or authorization != f"Bearer {LOCAL_DEV_TOKEN}":
        raise HTTPException(status_code=401, detail="Unauthorized: local-dev token required")
    return authorization


_dashboard_state = get_dashboard_state()


@control_plane_api.get("/status")
async def control_plane_status(authorization: str = Header(None)) -> Dict[str, Any]:
    """Control plane status: admission, capacity, kill-switch, budget."""
    _require_dev_auth(authorization)
    return {
        "admission": {
            "enabled": True,
            "tier": "GOVERNED",
            "last_check": datetime.now(timezone.utc).isoformat(),
        },
        "capacity": {
            "allocated": "alloc-demo-1",
            "granted": True,
            "resource_profile": {"cpu_cores": 1.0, "memory_mb": 512},
        },
        "kill_switch": {
            "killed": False,
            "quarantined": False,
            "reason": "",
        },
        "budget": {
            "spent": 0.0,
            "limit": 100.0,
            "currency": "usd",
            "remaining": 100.0,
            "tripped": False,
        },
        "evidence_label": "simulated",
        "_demo": True,
    }


@control_plane_api.get("/admission")
async def admission_status(authorization: str = Header(None)) -> Dict[str, Any]:
    """Current admission state."""
    _require_dev_auth(authorization)
    return {
        "enabled": True,
        "tier": "GOVERNED",
        "checks": 0,
        "denials": 0,
        "evidence_label": "simulated",
        "_demo": True,
    }
