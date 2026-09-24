#!/usr/bin/env python3
"""Hermetic receipt-chain deepen quickstart (PR #182)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from thinkbox.kilo_pr182_receipt_chain_deepen import receipt_chain_deepen_contract_summary
from thinkbox.receipt_chain_deepen.deepen_status_report import run_hermetic_deepen_demo
from thinkbox.receipt_chain_deepen.integrate import run_feature_demo


def main() -> None:
    demo = run_feature_demo("cassette")
    report = run_hermetic_deepen_demo()
    gate = receipt_chain_deepen_contract_summary()
    print(
        json.dumps(
            {
                "cassette": demo,
                "status": {
                    "live_verified": report.get("live_verified"),
                    "live_api_called": report.get("live_api_called"),
                },
                "gate_ok": gate.get("hermetic_operator_ok"),
            },
            indent=2,
            sort_keys=True,
        ),
    )


if __name__ == "__main__":
    main()
