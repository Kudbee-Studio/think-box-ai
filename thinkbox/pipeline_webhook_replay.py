"""Webhook delivery replay detection for GitHub lifecycle webhooks."""

from __future__ import annotations

import hashlib
import threading
from typing import Optional

from thinkbox.org_memory_receipts import OrgMemoryReceiptStore
from thinkbox.pipeline_store_lock import serialized_org_memory_write

WEBHOOK_DELIVERY_ACTION = "pipeline_webhook_delivery"

_seen: set[str] = set()
_lock = threading.Lock()


def delivery_id_fingerprint(delivery_id: str) -> str:
    """Stable fingerprint for org-memory storage (no raw delivery id in receipts)."""
    return hashlib.sha256(delivery_id.encode("utf-8")).hexdigest()[:32]


def register_delivery(
    delivery_id: str,
    store: Optional[OrgMemoryReceiptStore] = None,
) -> bool:
    """
    Return True if this delivery should be processed (first sight).

    When ``store`` is provided, deduplication is durable in org-memory (survives
    process restart; shared across workers using the same ``THINKBOX_ORG_MEMORY_DB``).

    Without ``store``, only an in-process cache applies (hermetic unit tests).
    """
    if not delivery_id:
        return True

    if store is None:
        with _lock:
            if delivery_id in _seen:
                return False
            _seen.add(delivery_id)
        return True

    fp = delivery_id_fingerprint(delivery_id)
    with serialized_org_memory_write():
        if store.has_webhook_delivery_fingerprint(fp):
            return False
        store.append_lifecycle(
            run_id="webhook_delivery",
            pr_number=0,
            branch="control-plane",
            from_state="RUNNING",
            to_state="RUNNING",
            action=WEBHOOK_DELIVERY_ACTION,
            result="recorded",
            evidence_label="simulated",
            evidence={
                "delivery_id_fingerprint": fp,
                "github_merge": False,
                "auto_merge": False,
            },
        )
    return True


def reset_replay_cache() -> None:
    """Clear in-process cache only (does not mutate org-memory receipts)."""
    with _lock:
        _seen.clear()


def is_replay(delivery_id: Optional[str], store: Optional[OrgMemoryReceiptStore] = None) -> bool:
    if not delivery_id:
        return False
    if store is not None:
        return store.has_webhook_delivery_fingerprint(delivery_id_fingerprint(delivery_id))
    with _lock:
        return delivery_id in _seen
