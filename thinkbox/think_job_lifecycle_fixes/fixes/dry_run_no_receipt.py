"""FIX07: dry_run must not persist receipts."""
from __future__ import annotations
from typing import Any

def dry_run_persists_receipt(dry_run: bool) -> bool:
    return not dry_run

def apply_fix() -> dict[str, Any]:
    return {
        "fix_id": "FIX07",
        "dry_run_no_persist": not dry_run_persists_receipt(True),
        "live_api_called": False,
    }
