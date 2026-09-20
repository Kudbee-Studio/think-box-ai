"""Request-merge replay protection beyond idempotency keys."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Optional

from thinkbox.org_memory_receipts import OrgMemoryReceiptStore


def merge_request_fingerprint(
    pr_number: int,
    branch: str,
    idempotency_key: str,
    founder_proof_hash: str,
) -> str:
    body = json.dumps(
        {
            "pr": pr_number,
            "branch": branch,
            "idem": idempotency_key,
            "proof": founder_proof_hash,
        },
        sort_keys=True,
    ).encode()
    return hashlib.sha256(body).hexdigest()[:24]


def find_replay_receipt(
    store: OrgMemoryReceiptStore,
    pr_number: int,
    fingerprint: str,
    *,
    limit: int = 40,
) -> Optional[dict[str, Any]]:
    if not fingerprint:
        return None
    for row in store.query(pr_number=pr_number, limit=limit):
        if str(row.get("action") or "") != "founder_merge_requested":
            continue
        evidence = row.get("evidence") or {}
        if str(evidence.get("replay_fingerprint") or "") == fingerprint:
            return row
    return None
