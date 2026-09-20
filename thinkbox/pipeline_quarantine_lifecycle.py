"""Quarantine lifecycle provenance from org-memory."""

from __future__ import annotations

from typing import Any

from thinkbox.org_memory_receipts import OrgMemoryReceiptStore


def quarantine_history(store: OrgMemoryReceiptStore, *, limit: int = 100) -> list[dict[str, Any]]:
    rows = store.query(limit=limit)
    history: list[dict[str, Any]] = []
    for row in reversed(rows):
        if str(row.get("action") or "") != "pipeline_quarantine":
            continue
        evidence = row.get("evidence") or {}
        history.append(
            {
                "timestamp": row.get("timestamp"),
                "quarantined": evidence.get("quarantined"),
                "reason": evidence.get("reason"),
                "agent_id": evidence.get("agent_id"),
                "entry_hash": row.get("entry_hash"),
            }
        )
    return history
