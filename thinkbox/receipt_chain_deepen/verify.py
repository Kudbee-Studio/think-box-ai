"""Chain verify wrapper (PR #182 F07)."""

from __future__ import annotations

from typing import Any

from thinkbox.receipt_chain_deepen.hash_link import GENESIS_HASH, compute_entry_hash, validate_link
from thinkbox.receipt_chain_deepen.append import HermeticReceiptChain


def verify_hermetic_chain(chain: HermeticReceiptChain) -> dict[str, Any]:
    prev = GENESIS_HASH
    issues: list[str] = []
    for i, row in enumerate(chain.entries()):
        if not validate_link(str(row.get("prev_hash")), prev):
            issues.append(f"gap at {i}")
        payload = {k: v for k, v in row.items() if k != "entry_hash"}
        expected = compute_entry_hash(payload)
        if expected != row.get("entry_hash"):
            issues.append(f"tamper at {i}")
        prev = str(row.get("entry_hash"))
    return {
        "valid": len(issues) == 0,
        "receipts": len(chain.entries()),
        "issues": issues,
        "live_api_called": False,
    }


def verify_store_chain_if_available() -> dict[str, Any]:
    """Optional bridge to ActionReceiptStore when present (in-memory temp only)."""
    from thinkbox.agent.control_plane.store import ActionReceiptStore
    from thinkbox.agent.control_plane.verify_chain import verify_chain

    store = ActionReceiptStore(":memory:")
    try:
        store.append("dry_run", "ok", "", "simulated", metadata={"hermetic": True})
        result = verify_chain(store)
        return {
            "valid": result.valid,
            "receipts": result.receipts,
            "issues": list(result.issues),
            "live_api_called": False,
        }
    finally:
        store.close()
