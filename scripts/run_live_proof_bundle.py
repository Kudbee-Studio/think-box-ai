#!/usr/bin/env python3
"""Run one bounded governed ``upcloud-ssh`` command and commit a redacted live-proof bundle.

This is the operator half of Phase 3 item 4: it executes exactly one allow-listed
read-only command on the UpCloud worker through the existing
``UpCloudSSHExecutionAdapter`` (no new path), then hands the raw artifact, receipt
and checkpoint to :mod:`thinkbox.live_proof_bundle` and writes the redacted bundle
into ``docs/evidence/live-proof/``.

Usage::

    python3 scripts/run_live_proof_bundle.py --command hostname
    python3 scripts/run_live_proof_bundle.py --command 'uname -a' --dry-run

``--dry-run`` validates configuration and prints what would run without executing.
Secrets never print: only the command, exit code, and artifact hash appear.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from thinkbox.live_proof_bundle import (
    LiveProofBundleError,
    build_live_proof_bundle,
    default_evidence_dir,
    write_live_proof_bundle,
)
from thinkbox.repository import Repository
from thinkbox.upcloud_ssh_execution_adapter import UpCloudSSHExecutionAdapter

ALLOWED_COMMANDS: tuple[str, ...] = (
    "hostname",
    "uname -a",
    "uptime",
    "whoami",
    "df -h /",
    "free -m",
)
DEFAULT_ARTIFACT_NAME = "governed_exec.json"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_receipt_from_checkpoint(repo: Repository, checkpoint_id: str) -> dict:
    path = repo.path / ".thinkbox" / "checkpoints" / f"{checkpoint_id}.json"
    if not path.is_file():
        raise LiveProofBundleError(f"checkpoint not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--command", required=True, help="one exactly-allowed read-only command")
    parser.add_argument("--dry-run", action="store_true", help="validate config, do not execute")
    parser.add_argument("--output-dir", default=None, help="bundle output dir (default docs/evidence/live-proof)")
    args = parser.parse_args()

    if args.command not in ALLOWED_COMMANDS:
        print(json.dumps({"ok": False, "error": f"command not allowed: {args.command!r}"}, indent=2))
        return 2

    repo = Repository(REPO_ROOT)
    adapter = UpCloudSSHExecutionAdapter(repo=repo)
    if not adapter.is_configured():
        cfg = adapter._config  # read-only diagnostic; no secret values are printed
        hardened_without_known_hosts = cfg.hardened and not cfg.known_hosts_path
        print(
            json.dumps(
                {
                    "ok": False,
                    "error": "upcloud-ssh not configured",
                    "required": ["UPCLOUD_SERVER_IP set to the worker-02 address", "UPCLOUD_SSH_KEY_PATH existing file"],
                    "hardened": cfg.hardened,
                    "hardened_without_known_hosts": hardened_without_known_hosts,
                    "hint": (
                        "hardened mode requires UPCLOUD_SSH_KNOWN_HOSTS to pin the host key"
                        if hardened_without_known_hosts
                        else "the env in this worktree points at the historical dead host; set the worker-02 values"
                    ),
                },
                indent=2,
            )
        )
        return 3

    print(
        json.dumps(
            {
                "ok": True,
                "phase": "ready",
                "command": args.command,
                "dry_run": args.dry_run,
                "hardened": adapter._config.hardened,
            },
            indent=2,
        )
    )
    if args.dry_run:
        return 0

    receipt = adapter.execute(job_id="live-proof-bundle", command=args.command, artifact_name=DEFAULT_ARTIFACT_NAME)
    receipt_dict = {
        "job_id": receipt.job_id,
        "execution_id": receipt.execution_id,
        "provider": receipt.provider,
        "status": receipt.status,
        "verified": receipt.verified,
        "exit_code": receipt.exit_code,
        "start_time": receipt.start_time,
        "end_time": receipt.end_time,
        "artifact_name": receipt.artifact_name,
        "artifact_hash": receipt.artifact_hash,
        "artifact_path": receipt.artifact_path,
        "checkpoint_id": receipt.checkpoint_id,
        "receipt_path": receipt.receipt_path,
        "provenance": list(receipt.provenance),
    }
    print(json.dumps({"phase": "executed", "status": receipt.status, "artifact_hash": receipt.artifact_hash}, indent=2))

    artifact_path = Path(receipt.artifact_path) if receipt.artifact_path else None
    if artifact_path is None or not artifact_path.is_file():
        print(json.dumps({"ok": False, "error": "no artifact produced"}, indent=2))
        return 4

    checkpoint = None
    if receipt.checkpoint_id:
        checkpoint = _load_receipt_from_checkpoint(repo, receipt.checkpoint_id)

    try:
        result = build_live_proof_bundle(
            artifact_path,
            receipt_dict,
            checkpoint,
            recorded_at=_now_iso(),
        )
    except LiveProofBundleError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, indent=2))
        return 5

    out_dir = Path(args.output_dir) if args.output_dir else default_evidence_dir(REPO_ROOT)
    json_path, md_path = write_live_proof_bundle(result, out_dir)
    print(
        json.dumps(
            {
                "ok": True,
                "bundle": str(json_path.relative_to(REPO_ROOT)),
                "summary": str(md_path.relative_to(REPO_ROOT)),
                "warnings": list(result.warnings),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
