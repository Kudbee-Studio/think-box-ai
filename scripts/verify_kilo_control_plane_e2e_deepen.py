#!/usr/bin/env python3
"""Hermetic operator gate: control-plane E2E deepen (PR #162)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from thinkbox.kilo_control_plane_e2e_deepen import control_plane_e2e_deepen_contract_summary
from thinkbox.kilo_hermetic_subprocess import enable_nested_e2e_unittest

enable_nested_e2e_unittest()


def main() -> int:
    summary = control_plane_e2e_deepen_contract_summary()
    print(json.dumps(summary, indent=2, sort_keys=True))
    if not summary.get("hermetic_operator_ok"):
        return 1
    if summary.get("live_verified", True):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
