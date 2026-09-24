"""FIX08: Shared etag across tabs stub (PR #140 parity)."""

from __future__ import annotations

from typing import Any


def shared_etag_stub(tab_id: str, etag: str) -> dict[str, Any]:
    return {
        "tab_id": tab_id,
        "etag": etag,
        "shared": True,
        "live_api_called": False,
    }


def apply_fix() -> dict[str, Any]:
    return {"fix_id": "FIX08", **shared_etag_stub("tab-a", '"W/\"demo\"')}
