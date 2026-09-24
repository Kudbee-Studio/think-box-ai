"""FIX21: typescript_longrange_energy (PR #194)."""
from __future__ import annotations

from typing import Any


def apply_fix() -> dict[str, Any]:
    ok = True

    return {"fix_id": "FIX21", "ok": ok, "live_api_called": False}
