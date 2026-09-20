"""Recovery/reconciliation helpers for pipeline org-memory."""

from __future__ import annotations

from typing import Any

from thinkbox.org_memory_receipts import OrgMemoryReceiptStore


def reconcile_overview_chain(store: OrgMemoryReceiptStore) -> dict[str, Any]:
    """Re-read chain verify + receipt counts for operator recovery."""
    count = store.count()
    valid = store.verify()
    prs = store.distinct_pr_numbers()
    return {
        "receipt_count": count,
        "chain_verified": valid,
        "distinct_pr_count": len(prs),
        "action": "reconcile_read_only",
        "mutated": False,
        "evidence_label": "simulated",
        "auto_merge": False,
    }
