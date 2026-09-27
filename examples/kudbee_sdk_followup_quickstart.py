#!/usr/bin/env python3
"""Hermetic Kudbee SDK follow-up quickstart (PR #179)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from thinkbox.kilo_pr179_kudbee_sdk_followup import kudbee_sdk_followup_contract_summary
from thinkbox.kudbee_sdk_followup.sdk_status_report import run_hermetic_sdk_demo


def main() -> None:
    gate = kudbee_sdk_followup_contract_summary()
    demo = run_hermetic_sdk_demo()
    print(json.dumps({"gate": gate, "demo": demo}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
