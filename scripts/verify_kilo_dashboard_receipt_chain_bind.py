#!/usr/bin/env python3
"""Print KILO dashboard receipt-chain bind contract summary (PR #156, hermetic)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from thinkbox.kilo_dashboard_receipt_chain_bind import (
    dashboard_receipt_chain_bind_contract_summary,
)
from thinkbox.kilo_receipt_chain_etag import hermetic_receipt_chain_etag_check


def main() -> int:
    prior = hermetic_receipt_chain_etag_check()
    if not prior.ok:
        print(json.dumps({"error": "prior receipt-chain-etag failed"}, indent=2))
        return 1

    summary = dashboard_receipt_chain_bind_contract_summary()
    summary["verify_mode"] = "hermetic_default"
    print(json.dumps(summary, indent=2, sort_keys=True))

    if not summary.get("hermetic_operator_ok"):
        return 1
    if summary.get("live_api_called"):
        return 1
    if not summary.get("verify_script_present"):
        return 1
    if not summary.get("gate_closed_default"):
        return 1
    if summary.get("end_link_api") != "END_LINK":
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
