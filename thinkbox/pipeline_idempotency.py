"""Client idempotency keys for founder merge requests."""

from __future__ import annotations

from thinkbox.org_memory_receipts import OrgMemoryReceiptStore


def find_merge_idempotency_receipt(
    store: OrgMemoryReceiptStore,
    pr_number: int,
    idempotency_key: str,
    *,
    limit: int = 50,
) -> dict | None:
    """Return newest matching queued merge receipt, if any."""
    if not idempotency_key:
        return None
    key = idempotency_key.strip()
    for row in store.query(pr_number=pr_number, limit=limit):
        if str(row.get("action") or "") != "founder_merge_requested":
            continue
        evidence = row.get("evidence") or {}
        if str(evidence.get("idempotency_key") or "") == key:
            return row
    return None
