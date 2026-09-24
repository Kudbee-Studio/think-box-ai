"""FIX11: Reject whitespace-only admission tokens."""
from __future__ import annotations
from typing import Any

def token_valid(token: str | None) -> bool:
    return bool(token and token.strip())

def apply_fix() -> dict[str, Any]:
    return {"fix_id": "FIX11", "ws_rejected": not token_valid("  "), "live_api_called": False}
