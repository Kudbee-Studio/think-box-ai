#!/usr/bin/env python3
"""Hermetic KUDBEECLI Phase 2 gate verify (PR #178)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from thinkbox.kilo_pr178_kudbee_cli_phase2 import kudbee_cli_phase2_contract_summary


def main() -> int:
    summary = kudbee_cli_phase2_contract_summary()
    print(json.dumps(summary, indent=2, sort_keys=True))
    if not summary.get("hermetic_operator_ok"):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
