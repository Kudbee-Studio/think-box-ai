"""FIX04: Surface receipt_id on governed run summaries."""
from __future__ import annotations
from typing import Any

def bridge_receipt(summary: dict[str, Any]) -> dict[str, Any]:
    receipt_id = summary.get("receipt_id")
    return {"receipt_id": receipt_id, "present": bool(receipt_id)}

def apply_fix() -> dict[str, Any]:
    bridged = bridge_receipt({"receipt_id": "rcpt_test"})
    return {"fix_id": "FIX04", "bridged": bridged["present"], "live_api_called": False}
