"""Head/tail receipt helpers (PR #182 F21)."""

from __future__ import annotations

from typing import Any


def head_tail(entries: list[dict[str, Any]]) -> dict[str, Any]:
    if not entries:
        return {"head": None, "tail": None, "count": 0, "live_api_called": False}
    return {
        "head": entries[0].get("receipt_id"),
        "tail": entries[-1].get("receipt_id"),
        "tail_hash": entries[-1].get("entry_hash"),
        "count": len(entries),
        "live_api_called": False,
    }
