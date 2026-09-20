"""Expanded integrity reports for pipeline control plane."""

from __future__ import annotations

from typing import Any

from thinkbox.org_memory_receipts import OrgMemoryReceiptStore
from thinkbox.pipeline_state_machine import state_machine_report


def expanded_pr_integrity(
    store: OrgMemoryReceiptStore,
    pr_number: int,
    *,
    receipt_limit: int = 500,
) -> dict[str, Any]:
    chain_ok = store.verify()
    rows = store.query(pr_number=pr_number, limit=receipt_limit)
    sm = state_machine_report(rows)
    actions: dict[str, int] = {}
    for row in rows:
        act = str(row.get("action") or "unknown")
        actions[act] = actions.get(act, 0) + 1
    return {
        "pr_number": pr_number,
        "receipt_count": len(rows),
        "chain_verified": chain_ok,
        "state_machine": sm,
        "action_histogram": actions,
        "first_entry_hash": rows[-1]["entry_hash"] if rows else "",
        "last_entry_hash": rows[0]["entry_hash"] if rows else "",
        "evidence_label": "verified" if chain_ok else "rejected",
        "auto_merge": False,
        "github_merge": False,
    }
