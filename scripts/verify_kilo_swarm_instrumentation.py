#!/usr/bin/env python3
"""Print KILO swarm-instrumentation contract summary (PR #147, hermetic operator gate)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from thinkbox.kilo_mercury_hermetic import hermetic_mercury_operator_check
from thinkbox.kilo_swarm_instrumentation import swarm_instrumentation_contract_summary


def main() -> int:
    mercury = hermetic_mercury_operator_check()
    if not mercury.ok:
        print(json.dumps({"error": "prior mercury-hermetic operator failed"}, indent=2))
        return 1
    summary = swarm_instrumentation_contract_summary()
    print(json.dumps(summary, indent=2, sort_keys=True))
    if not summary.get("hermetic_operator_ok"):
        return 1
    if summary.get("live_api_called"):
        return 1
    if summary.get("live_swarm_invoked"):
        return 1
    if not summary.get("eleven_of_eleven_hermetic"):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
