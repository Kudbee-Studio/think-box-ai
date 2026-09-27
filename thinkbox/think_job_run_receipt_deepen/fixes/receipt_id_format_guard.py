"""FIX01: Receipt id must be non-empty after strip."""
from __future__ import annotations
from typing import Any

def valid_receipt_id(value: str | None) -> bool:
    return bool(value and value.strip())

def apply_fix() -> dict[str, Any]:
    return {"fix_id": "FIX01", "ok": valid_receipt_id("rcpt_x") and not valid_receipt_id("  "), "live_api_called": False}
