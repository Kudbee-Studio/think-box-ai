#!/usr/bin/env python3
"""Hermetic enterprise lr-energy quickstart (PR #195)."""

from __future__ import annotations

import json

from thinkbox.kudbee_sdk_enterprise_lr_energy import enterprise_status_snapshot
from thinkbox.kilo_pr195_kudbee_sdk_enterprise_lr_energy import (
    kudbee_sdk_enterprise_lr_energy_contract_summary,
)


def main() -> None:
    contract = kudbee_sdk_enterprise_lr_energy_contract_summary()
    snap = enterprise_status_snapshot()
    print(
        json.dumps(
            {
                "contract_ok": contract["hermetic_operator_ok"],
                "snapshot": snap,
                "live_api_called": False,
            },
            indent=2,
            sort_keys=True,
        ),
    )


if __name__ == "__main__":
    main()
