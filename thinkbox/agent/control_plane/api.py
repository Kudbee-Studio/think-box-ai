"""Dashboard/API read of chain status — extends #98 control-plane routes."""

from __future__ import annotations

import json
import logging
from typing import Any

from thinkbox.agent.control_plane.store import ActionReceiptStore
from thinkbox.agent.control_plane.verify_chain import verify_chain, ChainResult

logger = logging.getLogger(__name__)


def chain_status(store: ActionReceiptStore) -> dict[str, Any]:
    """Read chain status for dashboard/API. evidence_label=simulated|_demo."""
    result = verify_chain(store)
    latest_receipts = store.latest(5)
    return {
        "chain_valid": result.valid,
        "total_receipts": result.receipts,
        "latest": latest_receipts,
        "issues": result.issues,
        "evidence_label": "simulated",
    }


def chain_health(store: ActionReceiptStore) -> dict[str, Any]:
    """Lightweight health check for dashboard panel."""
    result = verify_chain(store)
    return {
        "healthy": result.valid,
        "receipts": result.receipts,
        "gaps": len(result.gap_positions),
        "tampered": len(result.tampered_positions),
    }


def receipts_since(
    store: ActionReceiptStore,
    timestamp: str,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """Query receipts since a timestamp (for SSE/streaming)."""
    with store._lock:
        rows = store._conn.execute(
            "SELECT receipt_id, action, status, reason, evidence_label, timestamp, entry_hash FROM receipts WHERE timestamp >= ? ORDER BY rowid DESC LIMIT ?",
            (timestamp, limit),
        ).fetchall()
    return [
        {
            "receipt_id": r[0],
            "action": r[1],
            "status": r[2],
            "reason": r[3],
            "evidence_label": r[4],
            "timestamp": r[5],
            "entry_hash": r[6],
        }
        for r in rows
    ]
