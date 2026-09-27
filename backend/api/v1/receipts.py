"""Control plane: ActionReceipt hash-chain read API + verify."""

from datetime import datetime, timezone
from typing import Any, Dict, List

from fastapi import APIRouter, Header, HTTPException

LOCAL_DEV_TOKEN = "dev-only-local-token"

receipt_api = APIRouter(prefix="/api/v1/control-plane", tags=["control-plane"])


def _require_dev_auth(authorization: str = Header(None)) -> str:
    if not authorization or authorization != f"Bearer {LOCAL_DEV_TOKEN}":
        raise HTTPException(status_code=401, detail="Unauthorized")
    return authorization


@receipt_api.get("/receipts")
async def list_receipts(
    authorization: str = Header(None),
    limit: int = 50,
) -> Dict[str, Any]:
    """Latest N receipts."""
    _require_dev_auth(authorization)
    return {
        "receipts": [
            {
                "action_type": "ADMIT:AGENT_SPAWN",
                "agent_id": "demo-agent",
                "status": "OK",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "signature": "a" * 64,
                "previous_hash": "0" * 64,
                "think_job_receipt_id": "",
            },
        ],
        "total": 1,
        "limit": limit,
        "evidence_label": "simulated",
        "_demo": True,
    }


@receipt_api.get("/receipts/verify")
async def verify_chain(authorization: str = Header(None)) -> Dict[str, Any]:
    """Verify hash chain integrity."""
    _require_dev_auth(authorization)
    return {
        "valid": True,
        "error_code": "OK",
        "count": 1,
        "errors": [],
        "evidence_label": "simulated",
        "_demo": True,
    }
