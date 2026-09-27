"""FIX31: docker_bridge_defaults (PR #192)."""
from __future__ import annotations
from typing import Any

def apply_fix() -> dict[str, Any]:
    from thinkbox.kudbee_sdk_followup_w3.docker_bridge import describe_docker_compose_bridge
    d = describe_docker_compose_bridge()
    return {"fix_id": "FIX31", "ok": d["compose_service"] == "api", "live_api_called": False}
