"""Control-plane stub: last N org-memory lifecycle receipts for a PR (simulated evidence)."""

from __future__ import annotations

import os
import threading
from typing import Any, Optional

from fastapi import APIRouter, HTTPException

from thinkbox.org_memory_receipts import OrgMemoryReceiptStore

lifecycle_receipts_router = APIRouter(
    prefix="/api/v1/control-plane/lifecycle",
    tags=["control-plane", "lifecycle"],
)

_DEFAULT_DB = os.getenv(
    "THINKBOX_ORG_MEMORY_DB",
    os.path.join("data", "thinkboxmd", "db", "org_memory_receipts.db"),
)


_store: Optional[OrgMemoryReceiptStore] = None
_store_lock = threading.Lock()


def _get_store() -> OrgMemoryReceiptStore:
    global _store
    with _store_lock:
        if _store is None:
            _store = OrgMemoryReceiptStore(_DEFAULT_DB)
        return _store


@lifecycle_receipts_router.get("/receipts/pr/{pr_number}")
async def list_pr_lifecycle_receipts(
    pr_number: int,
    limit: int = 20,
) -> dict[str, Any]:
    """Last N redacted lifecycle receipts for a GitHub PR number."""
    if limit < 1 or limit > 200:
        raise HTTPException(status_code=400, detail="limit must be 1..200")
    store = _get_store()
    receipts = store.query(pr_number=pr_number, limit=limit)
    return {
        "pr_number": pr_number,
        "receipts": receipts,
        "count": len(receipts),
        "limit": limit,
        "evidence_label": "simulated",
        "chain_verified": store.verify(),
        "_stub": True,
    }


@lifecycle_receipts_router.get("/receipts/verify")
async def verify_org_memory_chain() -> dict[str, Any]:
    store = _get_store()
    return {
        "valid": store.verify(),
        "receipt_count": store.count(),
        "evidence_label": "simulated",
        "_stub": True,
    }
