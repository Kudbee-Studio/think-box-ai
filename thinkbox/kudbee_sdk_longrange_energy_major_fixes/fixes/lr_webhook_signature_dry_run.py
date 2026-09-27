"""FIX04: lr_webhook_signature_dry_run (PR #194)."""
from __future__ import annotations

from typing import Any


def apply_fix() -> dict[str, Any]:
    ok = True

    return {"fix_id": "FIX04", "ok": ok, "live_api_called": False}
