"""FIX12: Receipt GET path shape."""
from __future__ import annotations
from typing import Any

def receipt_path(receipt_id: str) -> str:
    return f"/api/v1/run/receipt/{receipt_id}"

def apply_fix() -> dict[str, Any]:
    return {"fix_id": "FIX12", "ok": receipt_path("r").endswith("/r"), "live_api_called": False}
