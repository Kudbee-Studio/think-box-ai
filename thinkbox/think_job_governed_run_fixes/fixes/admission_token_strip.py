"""FIX03: Admission token must strip whitespace."""
from __future__ import annotations
from typing import Any

def token_ok(token: str | None) -> bool:
    return bool(token and token.strip())

def apply_fix() -> dict[str, Any]:
    return {"fix_id": "FIX03", "ok": token_ok("t") and not token_ok("  "), "live_api_called": False}
