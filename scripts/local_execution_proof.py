#!/usr/bin/env python3
"""Operator local execution proof (no cloud credentials).

Writes a redacted JSON proof under ``data/local_execution/``.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from thinkbox.local_execution_adapter import (  # noqa: E402
    LocalExecutionAdapter,
    receipt_to_public_dict,
)
from thinkbox.repository import Repository

DEFAULT_COMMAND = "echo THINKBOX_LOCAL_EXECUTION_PROOF"
DEFAULT_OUT = REPO_ROOT / "data/local_execution/proof_latest.json"


def main() -> int:
    parser = argparse.ArgumentParser(description="Local Think Box execution proof")
    parser.add_argument("--worktree", default=str(REPO_ROOT), help="Git worktree path")
    parser.add_argument("--job-id", default="local_exec_proof", help="Think Job id")
    parser.add_argument("--command", default=DEFAULT_COMMAND, help="Bounded shell command")
    parser.add_argument("--artifact", default="local_proof.json", help="Artifact filename")
    parser.add_argument("--out", default=str(DEFAULT_OUT), help="Redacted proof output path")
    args = parser.parse_args()

    repo = Repository(Path(args.worktree))
    adapter = LocalExecutionAdapter(repo=repo)
    receipt = adapter.execute(
        job_id=args.job_id,
        command=args.command,
        artifact_name=args.artifact,
    )
    payload = receipt_to_public_dict(receipt)
    payload["timestamp"] = datetime.now(timezone.utc).isoformat()
    payload["gate_id"] = "local-execution-proof"
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2, sort_keys=True))
    print(f"proof_path: {out}")
    return 0 if receipt.status == "COMPLETED" and receipt.verified else 1


if __name__ == "__main__":
    sys.exit(main())
