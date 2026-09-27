#!/usr/bin/env python3
"""Quickstart for PR #186 run receipt deepen (hermetic)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from thinkbox.kilo_pr186_think_job_run_receipt_deepen import think_job_run_receipt_deepen_contract_summary
from thinkbox.think_job_run_receipt_deepen.cassette import replay_cassette
from thinkbox.think_job_run_receipt_deepen.deepen_status_report import think_job_run_receipt_deepen_status_report


def main() -> None:
    print(json.dumps(think_job_run_receipt_deepen_contract_summary(), indent=2, sort_keys=True))
    print(json.dumps(think_job_run_receipt_deepen_status_report(), indent=2, sort_keys=True))
    print(json.dumps(replay_cassette("receipt_deepen_flow.json"), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
