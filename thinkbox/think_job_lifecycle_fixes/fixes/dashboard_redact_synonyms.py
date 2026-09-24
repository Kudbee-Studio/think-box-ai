"""FIX22: Dashboard redaction includes token synonyms."""
from __future__ import annotations
from typing import Any

_REDACT_KEYS = frozenset({"token", "api_key", "authorization", "bearer"})

def should_redact(key: str) -> bool:
    return key.lower() in _REDACT_KEYS

def apply_fix() -> dict[str, Any]:
    return {"fix_id": "FIX22", "api_key": should_redact("api_key"), "live_api_called": False}
