#!/usr/bin/env python3
"""Operator probe for PR #201 — presence + optional live Box access.

Never prints secret values. Writes a redacted JSON artifact.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from thinkbox.upstash_box_access import (  # noqa: E402
    AccessClass,
    assert_no_secret_material,
    run_access_probe,
    write_evidence,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="PR #201 Upstash Box access probe")
    parser.add_argument(
        "--allow-network",
        action="store_true",
        help="Permit unauthenticated GET of the configured URL",
    )
    parser.add_argument(
        "--allow-execute",
        action="store_true",
        help="Permit one adapter POST /run when URL+token are configured",
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help="Mark this run as live HTTP (still requires configured adapter)",
    )
    parser.add_argument(
        "--out",
        default=str(REPO_ROOT / "data/upstash_box_access/probe_latest.json"),
        help="Redacted evidence output path",
    )
    args = parser.parse_args()

    report = run_access_probe(
        allow_network=args.allow_network,
        allow_execute=args.allow_execute,
        live_http_used=args.live,
    )
    payload = report.to_public_dict()
    import os

    assert_no_secret_material(payload, os.environ)
    dest = write_evidence(report, Path(args.out))
    print(json.dumps(payload, indent=2, sort_keys=True))
    print(f"evidence_path: {dest}")
    if report.classification is AccessClass.REMOTE_EXECUTION_VERIFIED and report.live_verified:
        return 0
    if report.classification is AccessClass.ENV_NOT_CONFIGURED:
        return 2
    return 1


if __name__ == "__main__":
    sys.exit(main())
