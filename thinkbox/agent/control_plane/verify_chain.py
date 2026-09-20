"""verify_chain() — detect gap, tamper, or fork in the receipt chain."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any

from thinkbox.agent.control_plane.store import ActionReceiptStore

logger = logging.getLogger(__name__)


@dataclass
class ChainResult:
    valid: bool
    receipts: int
    issues: list[str] = field(default_factory=list)
    gap_positions: list[int] = field(default_factory=list)
    tampered_positions: list[int] = field(default_factory=list)


def verify_chain(store: ActionReceiptStore) -> ChainResult:
    """Replay the receipt chain and detect gaps, tampering, or forks."""
    issues: list[str] = []
    gap_positions: list[int] = []
    tampered_positions: list[int] = []

    with store._lock:
        rows = store._conn.execute(
            "SELECT receipt_id, action, status, reason, evidence_label, timestamp, prev_hash, entry_hash, metadata FROM receipts ORDER BY rowid"
        ).fetchall()

    prev = "GENESIS"
    for i, row in enumerate(rows):
        receipt_id, action, status, reason, evidence_label, timestamp, prev_hash, entry_hash, metadata_str = row
        if prev_hash != prev:
            issues.append(f"gap at position {i}: receipt {receipt_id} prev_hash={prev_hash} expected {prev}")
            gap_positions.append(i)
            continue
        payload = {
            "receipt_id": receipt_id,
            "action": action,
            "status": status,
            "reason": reason,
            "evidence_label": evidence_label,
            "timestamp": timestamp,
            "prev_hash": prev_hash,
            "metadata": json.loads(metadata_str),
        }
        expected_hash = store._compute_hash(payload)
        if expected_hash != entry_hash:
            issues.append(f"tampered at position {i}: receipt {receipt_id}")
            tampered_positions.append(i)
        prev = entry_hash

    valid = len(issues) == 0
    if not valid:
        logger.warning("Chain verification failed: %s", issues)
    return ChainResult(
        valid=valid,
        receipts=len(rows),
        issues=issues,
        gap_positions=gap_positions,
        tampered_positions=tampered_positions,
    )
