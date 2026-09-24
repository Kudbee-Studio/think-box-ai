"""Feature registry integration (PR #182 F24)."""

from __future__ import annotations

from typing import Any

from thinkbox.receipt_chain_deepen.append import HermeticReceiptChain, append_receipt
from thinkbox.receipt_chain_deepen.cassette import replay_cassette
from thinkbox.receipt_chain_deepen.fork_detect import detect_fork_stub
from thinkbox.receipt_chain_deepen.negotiation import RECEIPT_CHAIN_DEEPEN_VERSION
from thinkbox.receipt_chain_deepen.replay import replay_actions
from thinkbox.receipt_chain_deepen.verify import verify_hermetic_chain

_FEATURE_HANDLERS: dict[str, str] = {
    "append": "append_receipt",
    "verify": "verify_hermetic_chain",
    "cassette": "replay_cassette",
    "fork": "detect_fork_stub",
    "replay": "replay_actions",
}


def list_registered_features() -> tuple[str, ...]:
    return tuple(sorted(_FEATURE_HANDLERS.keys()))


def run_feature_demo(feature_id: str) -> dict[str, Any]:
    if feature_id == "append":
        chain = HermeticReceiptChain()
        row = append_receipt(chain, "r-demo", "dry_run")
        return {"entry_hash": row.get("entry_hash"), "live_api_called": False}
    if feature_id == "verify":
        chain = HermeticReceiptChain()
        append_receipt(chain, "r-1", "a")
        return verify_hermetic_chain(chain)
    if feature_id == "cassette":
        return replay_cassette("chain_append_flow.json")
    if feature_id == "fork":
        report = detect_fork_stub("hash-a", "hash-b")
        return {"fork_detected": report.fork_detected, "live_api_called": False}
    if feature_id == "replay":
        return replay_actions([{"receipt_id": "r-x", "action": "noop"}])
    return {"error": "unknown_feature", "feature_id": feature_id, "live_api_called": False}


def integration_summary() -> dict[str, Any]:
    from thinkbox.receipt_chain_deepen.deepen_status_report import route_catalog_deepen

    return {
        "receipt_chain_deepen_version": RECEIPT_CHAIN_DEEPEN_VERSION,
        "registered_features": list(list_registered_features()),
        "routes": route_catalog_deepen(),
        "live_api_called": False,
        "dry_run": True,
    }
