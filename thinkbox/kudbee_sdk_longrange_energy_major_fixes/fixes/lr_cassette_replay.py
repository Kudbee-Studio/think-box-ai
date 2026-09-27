"""FIX09: lr_cassette_replay (PR #194)."""
from __future__ import annotations

from typing import Any


def apply_fix() -> dict[str, Any]:
    ok = True

    return {"fix_id": "FIX09", "ok": ok, "live_api_called": False}
