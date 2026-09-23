#!/usr/bin/env python3
"""Print KILO proof-schema contract summary (PR #148, hermetic operator gate)."""

# Hermetic operator gate — layers swarm-instrumentation; no live API calls.
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from thinkbox.kilo_proof_schema import proof_schema_contract_summary
from thinkbox.kilo_swarm_instrumentation import hermetic_swarm_operator_check


def main() -> int:
    swarm = hermetic_swarm_operator_check()
    if not swarm.ok:
        print(json.dumps({"error": "prior swarm-instrumentation operator failed"}, indent=2))
        return 1
    summary = proof_schema_contract_summary()
    print(json.dumps(summary, indent=2, sort_keys=True))
    if not summary.get("hermetic_operator_ok"):
        return 1
    if summary.get("live_api_called"):
        return 1
    if not summary.get("verify_script_present"):
        return 1
    if not summary.get("gate_closed_default"):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
