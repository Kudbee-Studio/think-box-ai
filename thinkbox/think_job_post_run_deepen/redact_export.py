"""Redact run responses (PR #184 F18)."""
from __future__ import annotations
import re
from typing import Any, Mapping

_TOKEN = re.compile(r"Bearer\s+\S+", re.I)

def redact_run_response(doc: Mapping[str, Any]) -> dict[str, Any]:
    out = dict(doc)
    for k in ("governance_token", "api_key"):
        if k in out:
            out[k] = "[REDACTED]"
    msg = str(out.get("message", ""))
    out["message"] = _TOKEN.sub("Bearer [REDACTED]", msg)
    return {"response": out, "redacted": True, "live_api_called": False}
