"""FIX17: Fail-closed empty receipt watch keys."""

from __future__ import annotations

from typing import Any

from thinkbox.think_job_status_ui import normalize_receipt_key


def watchable_receipt(raw: str) -> dict[str, Any]:
    try:
        key = normalize_receipt_key(raw)
    except ValueError:
        return {"watchable": False, "receipt_key": "", "live_api_called": False}
    return {
        "watchable": bool(key),
        "receipt_key": key,
        "live_api_called": False,
    }


def apply_fix() -> dict[str, Any]:
    empty = watchable_receipt("   ")
    valid = watchable_receipt(" rcpt-1 ")
    return {
        "fix_id": "FIX17",
        "empty_watchable": empty["watchable"],
        "valid_watchable": valid["watchable"],
        "live_api_called": False,
    }
