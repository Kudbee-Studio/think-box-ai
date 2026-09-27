#!/usr/bin/env python3
"""Hermetic KUDBEECLI Phase 3 quickstart (PR #180). No network."""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from thinkbox.cli_phase3.cassette import replay_cassette
from thinkbox.cli_phase3.status_report import cli_phase3_status_report
from thinkbox.kilo_pr180_kudbee_cli_phase3 import kudbee_cli_phase3_contract_summary


def main() -> None:
    summary = kudbee_cli_phase3_contract_summary()
    print(json.dumps({"gate": summary["gate_id"], "ok": summary["hermetic_operator_ok"]}, indent=2))
    report = cli_phase3_status_report()
    print(json.dumps({"profile": report["profile"], "live_api_called": report["live_api_called"]}))
    replay = replay_cassette("health_flow")
    print(json.dumps({"cassette": replay["cassette"], "replayed": replay["replayed"]}))


if __name__ == "__main__":
    main()
