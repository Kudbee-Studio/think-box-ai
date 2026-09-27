#!/usr/bin/env python3
"""Print KILO live-smoke-operator contract summary (PR #153, hermetic operator gate)."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from thinkbox.kilo_live_proof_exec import FOUNDER_ACK_ENV, live_exec_env_ready
from thinkbox.kilo_live_smoke_evidence import hermetic_live_smoke_evidence_operator_check
from thinkbox.kilo_live_smoke_operator import live_smoke_operator_contract_summary
from thinkbox.kilo_substrate_checklist import BOX_URL_ENV


def main() -> int:
    parser = argparse.ArgumentParser(description="KILO live-smoke-operator hermetic verify")
    parser.add_argument(
        "--live",
        action="store_true",
        help="Check live-prep env only (no HTTP); fail-closed without ack+URL",
    )
    args = parser.parse_args()

    smoke = hermetic_live_smoke_evidence_operator_check()
    if not smoke.ok:
        print(json.dumps({"error": "prior live-smoke-evidence operator failed"}, indent=2))
        return 1

    summary = live_smoke_operator_contract_summary()
    summary["verify_mode"] = "live_prep_check" if args.live else "hermetic_default"
    print(json.dumps(summary, indent=2, sort_keys=True))

    if not summary.get("hermetic_operator_ok"):
        return 1
    if summary.get("live_api_called"):
        return 1
    if not summary.get("verify_script_present"):
        return 1
    if not summary.get("operator_cli_present"):
        return 1
    if not summary.get("gate_closed_default"):
        return 1

    if args.live:
        env = dict(os.environ)
        ready = live_exec_env_ready(env)
        if not ready:
            print(
                json.dumps(
                    {
                        "live_path": "closed",
                        "reason": f"missing {FOUNDER_ACK_ENV} and/or {BOX_URL_ENV}",
                        "live_api_called": False,
                        "probe_steps": [
                            "python3 scripts/kilo_live_smoke_operator.py write",
                            "python3 scripts/kilo_live_smoke_operator.py audit-flip-candidate",
                        ],
                    },
                    indent=2,
                ),
                file=sys.stderr,
            )
            return 1
        print(
            json.dumps(
                {
                    "live_path": "env_ready_only",
                    "note": "no network calls from this script",
                    "live_api_called": False,
                },
                indent=2,
            ),
            file=sys.stderr,
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
