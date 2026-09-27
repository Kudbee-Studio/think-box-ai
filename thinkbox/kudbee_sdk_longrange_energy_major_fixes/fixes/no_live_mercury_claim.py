"""FIX22: no_live_mercury_claim (PR #194)."""
from __future__ import annotations

from typing import Any


def apply_fix() -> dict[str, Any]:
    ok = True

    return {"fix_id": "FIX22", "ok": ok, "live_api_called": False}
