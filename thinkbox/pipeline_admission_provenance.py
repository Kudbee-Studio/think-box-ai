"""Admission decision provenance — structured audit trail from org-memory."""

from __future__ import annotations

from typing import Any, Optional

from thinkbox.org_memory_receipts import OrgMemoryReceiptStore


def collect_admission_provenance(
    store: OrgMemoryReceiptStore,
    *,
    pr_number: Optional[int] = None,
    limit: int = 200,
) -> list[dict[str, Any]]:
    """Chronological admission-related receipts (oldest first)."""
    if pr_number is not None:
        rows = store.query(pr_number=pr_number, limit=limit)
    else:
        rows = store.query(limit=limit)
    events: list[dict[str, Any]] = []
    for row in reversed(rows):
        action = str(row.get("action") or "")
        if action not in (
            "admission_denied",
            "merge_request_denied",
            "founder_merge_requested",
            "merge_policy_denied",
        ):
            continue
        evidence = row.get("evidence") or {}
        events.append(
            {
                "sequence": row.get("sequence"),
                "timestamp": row.get("timestamp"),
                "pr_number": row.get("pr_number"),
                "action": action,
                "result": row.get("result"),
                "agent_id": evidence.get("agent_id"),
                "capability": evidence.get("capability"),
                "admission_reason": evidence.get("admission_reason") or evidence.get("reason"),
                "evidence_label": row.get("evidence_label"),
                "entry_hash": row.get("entry_hash"),
                "github_merge": evidence.get("github_merge", False),
            }
        )
    return events


def provenance_summary(events: list[dict[str, Any]]) -> dict[str, Any]:
    admitted = sum(1 for e in events if e.get("action") == "founder_merge_requested")
    denied = sum(
        1
        for e in events
        if str(e.get("result") or "") == "blocked" or e.get("action") in ("admission_denied",)
    )
    return {
        "event_count": len(events),
        "merge_requests_queued": admitted,
        "denials": denied,
        "evidence_label": "simulated",
        "auto_merge": False,
    }
