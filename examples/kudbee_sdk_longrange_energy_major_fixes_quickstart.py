#!/usr/bin/env python3
"""Hermetic Kudbee SDK lr-energy major fixes quickstart (PR #194)."""

from __future__ import annotations

import json

from thinkbox.kilo_pr194_kudbee_sdk_longrange_energy_major_fixes import (
    kudbee_sdk_longrange_energy_major_fixes_contract_summary,
)
from thinkbox.kudbee_sdk_longrange_energy_major_fixes.fixes.fix_registry import run_all_fixes


def main() -> None:
    contract = kudbee_sdk_longrange_energy_major_fixes_contract_summary()
    fixes = run_all_fixes()
    print(
        json.dumps(
            {
                "contract_ok": contract["hermetic_operator_ok"],
                "fixes": fixes,
                "live_api_called": False,
            },
            indent=2,
            sort_keys=True,
        ),
    )


if __name__ == "__main__":
    main()
