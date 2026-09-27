"""Compaction stub for long chains (PR #182 F13)."""

from __future__ import annotations

from typing import Any


def compact_chain_stub(entries: list[dict[str, Any]], keep_tail: int = 8) -> dict[str, Any]:
    if keep_tail < 1:
        keep_tail = 1
    if len(entries) <= keep_tail:
        return {
            "compacted": False,
            "kept": len(entries),
            "entries": list(entries),
            "live_api_called": False,
        }
    tail = entries[-keep_tail:]
    return {
        "compacted": True,
        "kept": len(tail),
        "dropped": len(entries) - len(tail),
        "entries": tail,
        "anchor_hash": tail[0].get("prev_hash"),
        "live_api_called": False,
    }
