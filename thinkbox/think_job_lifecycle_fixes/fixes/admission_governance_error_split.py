"""FIX09: Split admission vs governance denial codes."""
from __future__ import annotations
from typing import Any

def error_codes() -> dict[str, str]:
    return {"admission_denied": "ADMISSION_DENIED", "governance_denied": "GOVERNANCE_DENIED"}

def apply_fix() -> dict[str, Any]:
    codes = error_codes()
    return {"fix_id": "FIX09", "distinct": codes["admission_denied"] != codes["governance_denied"], "codes": codes, "live_api_called": False}
