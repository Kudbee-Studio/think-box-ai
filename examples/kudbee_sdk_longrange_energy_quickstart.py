#!/usr/bin/env python3
"""Hermetic Kudbee SDK long-range + energy loops quickstart (PR #193)."""

from __future__ import annotations

import json

from thinkbox.kudbee_sdk_longrange_energy import KudbeeSdkLrEnergyClient
from thinkbox.kudbee_sdk_longrange_energy.sdk_status_report import run_hermetic_sdk_lr_energy_demo
from thinkbox.kilo_pr193_kudbee_sdk_longrange_energy import kudbee_sdk_longrange_energy_contract_summary


def main() -> None:
    contract = kudbee_sdk_longrange_energy_contract_summary()
    client = KudbeeSdkLrEnergyClient.from_env()
    demo = run_hermetic_sdk_lr_energy_demo()
    print(
        json.dumps(
            {
                "contract_ok": contract["hermetic_operator_ok"],
                "health": client.health(),
                "demo": demo,
                "live_api_called": False,
            },
            indent=2,
            sort_keys=True,
        ),
    )


if __name__ == "__main__":
    main()
