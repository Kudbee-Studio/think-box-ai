#!/usr/bin/env python3
"""Print KILO mercury-hermetic contract summary (PR #146, hermetic operator gate)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from thinkbox.kilo_governance_evidence import hermetic_governance_operator_check
from thinkbox.kilo_mercury_hermetic import mercury_hermetic_contract_summary


def main() -> int:
    gov = hermetic_governance_operator_check()
    if not gov.ok:
        print(json.dumps({"error": "prior governance-evidence operator failed"}, indent=2))
        return 1
    summary = mercury_hermetic_contract_summary()
    print(json.dumps(summary, indent=2, sort_keys=True))
    if not summary.get("hermetic_operator_ok"):
        return 1
    if summary.get("live_api_called"):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
