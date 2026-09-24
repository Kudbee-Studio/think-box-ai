#!/usr/bin/env python3
"""Governed local shell proof (explicit substrate=local, no cloud)."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from thinkbox.governed_job_execution import SUBSTRATE_LOCAL, execute_governed_job_command  # noqa: E402
from thinkbox.repository import Repository  # noqa: E402

DEFAULT_COMMAND = "echo THINKBOX_GOVERNED_LOCAL_PROOF"
DEFAULT_OUT = REPO_ROOT / "data/local_execution/governed_local_proof_latest.json"


def main() -> int:
    parser = argparse.ArgumentParser(description="Governed local execution proof")
    parser.add_argument("--worktree", default=str(REPO_ROOT))
    parser.add_argument("--job-id", default="governed_local_exec_proof")
    parser.add_argument("--command", default=DEFAULT_COMMAND)
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    args = parser.parse_args()

    result = execute_governed_job_command(
        substrate=SUBSTRATE_LOCAL,
        job_id=args.job_id,
        command=args.command,
        repo=Repository(Path(args.worktree)),
    )
    payload = dict(result.public_proof)
    payload["timestamp"] = datetime.now(timezone.utc).isoformat()
    payload["verdict"] = result.verdict
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2, sort_keys=True))
    print(f"proof_path: {out}")
    return 0 if result.verdict == "COMPLETED" else 1


if __name__ == "__main__":
    sys.exit(main())
