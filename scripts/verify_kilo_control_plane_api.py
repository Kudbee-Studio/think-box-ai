#!/usr/bin/env python3
"""Print KILO control-plane-api contract summary (PR #154, hermetic gate)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from thinkbox.kilo_control_plane_api import control_plane_api_contract_summary
from thinkbox.kilo_live_smoke_operator import hermetic_live_smoke_operator_check


def main() -> int:
    operator = hermetic_live_smoke_operator_check()
    if not operator.ok:
        print(json.dumps({"error": "prior live-smoke-operator failed"}, indent=2))
        return 1

    summary = control_plane_api_contract_summary()
    summary["verify_mode"] = "hermetic_default"
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
