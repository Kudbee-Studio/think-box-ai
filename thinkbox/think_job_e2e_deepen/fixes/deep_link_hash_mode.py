"""FIX09: Deep-link hash receipt watch mode honesty."""

from __future__ import annotations

from typing import Any

from thinkbox.control_plane_deep_link import build_think_job_watch_href


def apply_fix() -> dict[str, Any]:
    query_href = build_think_job_watch_href(receipt_id="rcpt-hash", use_hash_for_receipt=False)
    hash_href = build_think_job_watch_href(receipt_id="rcpt-hash", use_hash_for_receipt=True)
    return {
        "fix_id": "FIX09",
        "query_href": query_href,
        "hash_href": hash_href,
        "modes_distinct": query_href != hash_href,
        "live_api_called": False,
    }
