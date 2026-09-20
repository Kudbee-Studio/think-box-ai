"""Cross-check PR summary vs raw receipt rollups."""

from __future__ import annotations

from typing import Any

from thinkbox.org_memory_receipts import OrgMemoryReceiptStore
from thinkbox.pipeline_rollup import summarize_pr_from_receipts


def verify_pr_rollup_consistency(
    store: OrgMemoryReceiptStore,
    pr_number: int,
    *,
    receipt_limit: int = 300,
) -> dict[str, Any]:
    receipts = store.query(pr_number=pr_number, limit=receipt_limit)
    summary = summarize_pr_from_receipts(pr_number, receipts).to_dict()
    manual_admission = sum(
        1 for r in receipts if str(r.get("action") or "") == "admission_denied"
    )
    ok = int(summary.get("admission_denied_count") or 0) == manual_admission
    return {
        "pr_number": pr_number,
        "consistent": ok,
        "summary_admission_denied": summary.get("admission_denied_count"),
        "manual_admission_denied": manual_admission,
        "receipt_count": len(receipts),
        "evidence_label": "simulated",
    }
