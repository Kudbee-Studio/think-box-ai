"""Control-plane stub: last N org-memory lifecycle receipts for a PR (simulated evidence)."""

from __future__ import annotations

import os
from typing import Any

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


def _get_store() -> OrgMemoryReceiptStore:
    return OrgMemoryReceiptStore(_DEFAULT_DB)


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
