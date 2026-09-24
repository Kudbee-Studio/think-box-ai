"""FIX02: Session and experiment ids required together."""
from __future__ import annotations
from typing import Any

def pair_ok(session_id: str | None, experiment_id: str | None) -> bool:
    return bool(session_id and experiment_id)

def apply_fix() -> dict[str, Any]:
    return {"fix_id": "FIX02", "pair_ok": pair_ok("s", "e"), "live_api_called": False}
