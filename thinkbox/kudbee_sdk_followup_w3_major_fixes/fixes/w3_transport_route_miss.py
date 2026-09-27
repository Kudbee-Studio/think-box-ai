"""FIX15: w3_transport_route_miss (PR #192)."""
from __future__ import annotations
from typing import Any

def apply_fix() -> dict[str, Any]:
    from thinkbox.kudbee_sdk_followup_w3.transport import HttpResponse, InMemoryTransport
    t = InMemoryTransport(routes={})
    r = t.request("GET", "http://127.0.0.1/nope", {}, None, 1.0)
    return {"fix_id": "FIX15", "ok": r.status == 404, "live_api_called": False}
