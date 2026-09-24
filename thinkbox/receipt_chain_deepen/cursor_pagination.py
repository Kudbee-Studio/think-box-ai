"""Cursor pagination helpers wrapping receipt_chain_query (PR #182 F20)."""

from __future__ import annotations

from typing import Any

from thinkbox.receipt_chain_query import decode_cursor, encode_cursor


def pagination_roundtrip(rowid: int) -> dict[str, Any]:
    cursor = encode_cursor(rowid)
    decoded = decode_cursor(cursor)
    return {
        "rowid": rowid,
        "cursor": cursor,
        "decoded": decoded,
        "ok": decoded == rowid,
        "live_api_called": False,
    }


def slice_fixture_page(receipts: list[dict[str, Any]], start_rowid: int, limit: int) -> dict[str, Any]:
    page = receipts[start_rowid : start_rowid + limit]
    next_row = start_rowid + len(page)
    next_cursor = encode_cursor(next_row) if next_row < len(receipts) else None
    return {
        "receipts": page,
        "next_cursor": next_cursor,
        "total": len(receipts),
        "live_api_called": False,
    }
