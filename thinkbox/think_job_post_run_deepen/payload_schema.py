"""POST /run payload shape (PR #184 F05)."""
from __future__ import annotations
from typing import Any

REQUIRED = ("goal", "agent_id", "governance_token")

def validate_run_payload(body: dict[str, Any]) -> dict[str, Any]:
    missing = [k for k in REQUIRED if not str(body.get(k, "")).strip()]
    return {"valid": not missing, "missing": missing, "live_api_called": False}
