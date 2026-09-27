"""FIX08: If-Match precondition catalog stub for 412 paths."""
from __future__ import annotations
from typing import Any

def precondition_catalog() -> list[str]:
    return ["If-Match", "If-None-Match"]

def apply_fix() -> dict[str, Any]:
    return {"fix_id": "FIX08", "headers": precondition_catalog(), "live_api_called": False}
