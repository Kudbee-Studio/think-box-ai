#!/usr/bin/env python3
"""Hermetic Kudbee SDK wave 3 major fixes quickstart (PR #192)."""

from __future__ import annotations

import json

from thinkbox.kudbee_sdk_followup_w3_major_fixes.fixes.fix_registry import run_all_fixes
from thinkbox.kudbee_sdk_followup_w3_major_fixes.w3_major_status_report import w3_major_fixes_status_report
from thinkbox.kilo_pr192_kudbee_sdk_followup_w3_major_fixes import kudbee_sdk_followup_w3_major_fixes_contract_summary


def main() -> None:
    contract = kudbee_sdk_followup_w3_major_fixes_contract_summary()
    fixes = run_all_fixes()
    report = w3_major_fixes_status_report()
    print(
        json.dumps(
            {
                "contract_ok": contract["hermetic_operator_ok"],
                "fix_count": fixes["fix_count"],
                "all_hermetic": fixes["all_hermetic"],
                "report_gate": report["gate_id"],
                "live_api_called": False,
            },
            indent=2,
            sort_keys=True,
        ),
    )


if __name__ == "__main__":
    main()
