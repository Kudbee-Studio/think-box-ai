"""Aggregate status report for PR #182 (F25)."""

from __future__ import annotations

from typing import Any

from thinkbox.receipt_chain_deepen.audit_ledger_bridge import audit_ledger_bridge_summary
from thinkbox.receipt_chain_deepen.end_link_bridge import end_link_bridge_summary
from thinkbox.receipt_chain_deepen.etag_bridge import etag_bridge_summary
from thinkbox.receipt_chain_deepen.integrate import integration_summary
from thinkbox.receipt_chain_deepen.negotiation import RECEIPT_CHAIN_DEEPEN_VERSION
from thinkbox.receipt_chain_deepen.status_catalog import status_catalog


def route_catalog_deepen() -> list[dict[str, str]]:
    return [
        {"id": "deepen/status", "method": "GET", "hermetic": "true"},
        {"id": "deepen/cassette", "method": "GET", "hermetic": "true"},
        {"id": "deepen/dry-run/page", "method": "GET", "hermetic": "true"},
    ]


def receipt_chain_deepen_status_report() -> dict[str, Any]:
    return {
        "receipt_chain_deepen_version": RECEIPT_CHAIN_DEEPEN_VERSION,
        "integration": integration_summary(),
        "status_catalog": status_catalog(),
        "etag_bridge": etag_bridge_summary(),
        "end_link_bridge": end_link_bridge_summary(),
        "audit_ledger_bridge": audit_ledger_bridge_summary(),
        "live_verified": False,
        "live_api_called": False,
        "four_state_max": "TEST_VERIFIED",
    }


def run_hermetic_deepen_demo() -> dict[str, Any]:
    report = receipt_chain_deepen_status_report()
    report["demo"] = True
    return report
