#!/usr/bin/env python3
"""Hermetic Kudbee SDK follow-up wave 3 quickstart (PR #191)."""

from __future__ import annotations

import json

from thinkbox.kudbee_sdk_followup_w3 import KudbeeSdkFollowupW3Client
from thinkbox.kudbee_sdk_followup_w3.sdk_status_report import run_hermetic_sdk_w3_demo
from thinkbox.kilo_pr191_kudbee_sdk_followup_w3 import kudbee_sdk_followup_w3_contract_summary


def main() -> None:
    contract = kudbee_sdk_followup_w3_contract_summary()
    client = KudbeeSdkFollowupW3Client.from_env()
    demo = run_hermetic_sdk_w3_demo()
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
