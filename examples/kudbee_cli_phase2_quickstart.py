#!/usr/bin/env python3
"""Hermetic KUDBEECLI Phase 2 quickstart (PR #178)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from thinkbox.cli_phase2.inspect_status import cli_health_report
from thinkbox.kilo_pr178_kudbee_cli_phase2 import kudbee_cli_phase2_contract_summary


def main() -> None:
    gate = kudbee_cli_phase2_contract_summary()
    health = cli_health_report()
    print(json.dumps({"gate": gate, "health": health}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
