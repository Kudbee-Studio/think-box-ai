#!/usr/bin/env python3
"""Hermetic Kudbee SDK follow-up wave 3 gate verify (PR #191)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from thinkbox.kilo_pr191_kudbee_sdk_followup_w3 import kudbee_sdk_followup_w3_contract_summary


def main() -> int:
    summary = kudbee_sdk_followup_w3_contract_summary()
    print(json.dumps(summary, indent=2, sort_keys=True))
    if not summary.get("hermetic_operator_ok"):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
