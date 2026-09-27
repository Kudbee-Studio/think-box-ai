#!/usr/bin/env python3
"""Print KILO post-season-harden contract summary (PR #151, hermetic operator gate)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from thinkbox.kilo_live_proof_exec import hermetic_live_proof_exec_operator_check
from thinkbox.kilo_post_season_harden import post_season_harden_contract_summary


def main() -> int:
    live_exec = hermetic_live_proof_exec_operator_check()
    if not live_exec.ok:
        print(json.dumps({"error": "prior live-proof-exec operator failed"}, indent=2))
        return 1
    summary = post_season_harden_contract_summary()
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
