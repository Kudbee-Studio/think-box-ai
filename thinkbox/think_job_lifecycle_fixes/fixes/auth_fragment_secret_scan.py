"""FIX20: Detect Authorization fragments in export blobs."""
from __future__ import annotations
from typing import Any

_FORBIDDEN = ("Bearer ", "Authorization:")

def scan_blob(text: str) -> bool:
    return not any(tok in text for tok in _FORBIDDEN)

def apply_fix() -> dict[str, Any]:
    return {"fix_id": "FIX20", "clean": scan_blob("ok"), "dirty": not scan_blob("Bearer x"), "live_api_called": False}
