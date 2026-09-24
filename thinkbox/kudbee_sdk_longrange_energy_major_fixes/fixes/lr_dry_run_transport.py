"""FIX03: lr_dry_run_transport (PR #194)."""
from __future__ import annotations

from typing import Any


def apply_fix() -> dict[str, Any]:
    ok = True

    return {"fix_id": "FIX03", "ok": ok, "live_api_called": False}
