"""Deterministic chain replay (PR #182 F12)."""

from __future__ import annotations

from typing import Any

from thinkbox.receipt_chain_deepen.append import HermeticReceiptChain, append_receipt
from thinkbox.receipt_chain_deepen.verify import verify_hermetic_chain


def replay_actions(actions: list[dict[str, Any]]) -> dict[str, Any]:
    chain = HermeticReceiptChain()
    for i, act in enumerate(actions):
        append_receipt(
            chain,
            receipt_id=str(act.get("receipt_id") or f"r-{i}"),
            action=str(act.get("action") or "noop"),
            metadata=dict(act.get("metadata") or {}),
        )
    verification = verify_hermetic_chain(chain)
    return {
        "replayed": len(actions),
        "verification": verification,
        "live_api_called": False,
    }
