"""Dry-run bridge for control-plane receipt paths (PR #182 F16)."""

from __future__ import annotations

from typing import Any


def dry_run_chain_page(cursor: str | None = None, limit: int = 10) -> dict[str, Any]:
    from thinkbox.receipt_chain_deepen.fixtures import load_fixture

    doc = load_fixture("sample_chain_page.json")
    receipts = list(doc.get("receipts") or [])[: max(1, min(limit, 50))]
    return {
        "receipts": receipts,
        "next_cursor": doc.get("next_cursor"),
        "chain_valid": True,
        "dry_run": True,
        "cursor_in": cursor,
        "live_api_called": False,
    }
