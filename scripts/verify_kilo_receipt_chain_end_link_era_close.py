#!/usr/bin/env python3
"""Hermetic verify for PR #162 receipt-chain-end-link-era-close gate."""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from thinkbox.kilo_receipt_chain_end_link_era_close import (
    hermetic_receipt_chain_end_link_era_close_check,
    minimal_receipt_chain_end_link_era_close_environ,
    receipt_chain_end_link_era_close_contract_summary,
)


def main() -> int:
    env = minimal_receipt_chain_end_link_era_close_environ()
    result = hermetic_receipt_chain_end_link_era_close_check(env)
    summary = receipt_chain_end_link_era_close_contract_summary(env)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if result.ok else 1


if __name__ == "__main__":
    sys.exit(main())
