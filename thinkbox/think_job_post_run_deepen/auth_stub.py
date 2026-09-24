"""API key auth stub (PR #184 F07)."""
from __future__ import annotations
from typing import Any

def auth_ok(api_key: str | None, expected_prefix: str = "tb_") -> dict[str, Any]:
    key = (api_key or "").strip()
    return {"authorized": key.startswith(expected_prefix), "live_api_called": False}
