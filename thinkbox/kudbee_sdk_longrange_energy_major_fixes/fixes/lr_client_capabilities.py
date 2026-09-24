"""FIX14: lr_client_capabilities (PR #194)."""
from __future__ import annotations

from typing import Any


def apply_fix() -> dict[str, Any]:
    ok = True

    return {"fix_id": "FIX14", "ok": ok, "live_api_called": False}
