#!/usr/bin/env python3
"""Hermetic CI spine-trust gate verify (PR #172)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from thinkbox.kilo_pr172_ci_spine_trust import ci_spine_trust_contract_summary


def main() -> int:
    summary = ci_spine_trust_contract_summary()
    print(json.dumps(summary, indent=2, sort_keys=True))
    if not summary.get("hermetic_operator_ok"):
        return 1
    if summary.get("live_verified") or summary.get("live_api_called"):
        return 1
    if not summary.get("gate_closed_default"):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
