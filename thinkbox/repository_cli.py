"""Think CLI execution harness for repository and job control."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from thinkbox.repository import Repository
from thinkbox.execution_adapter import UpstashBoxExecutionAdapter
from thinkbox.local_execution_adapter import LocalExecutionAdapter


def _repository(args: argparse.Namespace) -> Repository:
    return Repository(args.worktree, enforce_git=False)


def _print_job(repo: Repository, job_id: str) -> None:
    status = repo.job_status(job_id)
    if status is None:
        print(f"job not found: {job_id}")
        sys.exit(1)
    for key in (
        "job_id", "worktree_id", "path", "name", "intent", "status",
        "next_action", "provenance", "checkpoint_ids", "created_at",
        "updated_at",
    ):
        value = status.get(key)
        if isinstance(value, list) and len(value) > 6:
            value = value[:6] + [f"...({len(value)} total)"]
        print(f"  {key}: {value}")
    print(f"  receipt_location: {repo.receipt(job_id)}")


def cmd_repo_inspect(args: argparse.Namespace) -> None:
    repo = _repository(args)
    repo.refresh_git_state()
    summary = repo.summary()
    worktree = summary["worktree"]
    print(f"repository_version: {summary['repository_version']}")
    print(f"worktree_id: {worktree['worktree_id']}")
    print(f"path: {worktree['path']}")
    print(f"name: {worktree['name']}")
    git_state = summary.get("git_state", {})
    print(f"git_branch: {git_state.get('branch', '')}")
    print(f"git_head: {git_state.get('head', '')}")
    print(f"status: {worktree['status']}")
    print(f"attached_session_id: {worktree['attached_session_id']}")
    print(f"current_job_id: {worktree['current_job_id']}")
    print(f"checkpoint_count: {summary['checkpoint_count']}")


def cmd_box_inspect(args: argparse.Namespace) -> None:
    repo = _repository(args)
    worktree = repo.worktree
    print(f"box_id: {worktree.worktree_id}")
    print(f"worktree_id: {worktree.worktree_id}")
    print(f"path: {worktree.path}")
    print(f"name: {worktree.name}")
    print(f"status: {worktree.status}")
    print(f"attached_session_id: {worktree.attached_session_id}")
    print(f"current_job_id: {worktree.current_job_id}")
    print(f"intent: {worktree.metadata.get('intent', '')}")
    print(f"checkpoint_count: {len(repo.checkpoints())}")
    print(f"created_at: {worktree.created_at}")


def cmd_job_create(args: argparse.Namespace) -> None:
    repo = _repository(args)
    job = repo.create_job(
        job_id=args.job_id,
        intent=args.intent,
        name=args.name or "",
    )
    print(f"job_id: {job.job_id}")
    print(f"worktree_id: {job.worktree_id}")
    print(f"path: {job.path}")
    print(f"status: {job.status}")
    print(f"next_action: {job.next_action}")
    print(f"created_at: {job.created_at}")
    print(f"updated_at: {job.updated_at}")


def cmd_job_status(args: argparse.Namespace) -> None:
    repo = _repository(args)
    _print_job(repo, args.job_id)


def cmd_job_checkpoint(args: argparse.Namespace) -> None:
    repo = _repository(args)
    checkpoint = repo.checkpoint(args.name, job_id=args.job_id)
    print(f"job_id: {args.job_id}")
    print(f"checkpoint_id: {checkpoint.checkpoint_id}")
    print(f"checkpoint_path: {repo.path / '.thinkbox/checkpoints' / f'{checkpoint.checkpoint_id}.json'}")
    print(f"name: {checkpoint.name}")


def cmd_job_receipt(args: argparse.Namespace) -> None:
    repo = _repository(args)
    receipt = repo.receipt(args.job_id)
    if receipt is None:
        print(f"no receipt found for job: {args.job_id}")
        sys.exit(1)
    print(f"job_id: {receipt['job_id']}")
    print(f"checkpoint_id: {receipt['checkpoint_id']}")
    print(f"receipt_path: {receipt['path']}")
    print(f"verified: {bool(receipt.get('content'))}")


def cmd_job_execute_local(args: argparse.Namespace) -> None:
    repo = _repository(args)
    adapter = LocalExecutionAdapter(repo=repo)
    print("local_execution: configured (no cloud credentials required)")
    receipt = adapter.execute(
        job_id=args.job_id,
        command=args.exec_command,
        artifact_name=args.artifact,
    )
    print(f"job_id: {receipt.job_id}")
    print(f"execution_id: {receipt.execution_id}")
    print(f"status: {receipt.status}")
    print(f"provider: {receipt.provider}")
    print(f"exit_code: {receipt.exit_code}")
    print(f"artifact_name: {receipt.artifact_name}")
    print(f"artifact_path: {receipt.artifact_path}")
    print(f"artifact_hash: {receipt.artifact_hash}")
    print(f"checkpoint_id: {receipt.checkpoint_id}")
    print(f"receipt_path: {receipt.receipt_path}")
    print(f"verified: {receipt.verified}")
    print(f"error: {receipt.error}")
    print("live_verified: False")


def cmd_job_execute(args: argparse.Namespace) -> None:
    repo = _repository(args)
    adapter = UpstashBoxExecutionAdapter(repo=repo)
    inventory = adapter.discover_env()
    print("upstash_env_inventory:")
    for name, present in inventory.items():
        print(f"  {name}: {present}")
    if not adapter.is_configured():
        print("status: NOT_CONFIGURED")
        print("result: remote execution is unavailable; no job executed")
        return
    receipt = adapter.execute(
        job_id=args.job_id,
        command=args.exec_command,
        artifact_name=args.artifact,
    )
    print(f"job_id: {receipt.job_id}")
    print(f"execution_id: {receipt.execution_id}")
    print(f"status: {receipt.status}")
    print(f"provider: {receipt.provider}")
    print(f"box_id: {receipt.box_id}")
    print(f"exit_code: {receipt.exit_code}")
    print(f"artifact_name: {receipt.artifact_name}")
    print(f"artifact_path: {receipt.artifact_path}")
    print(f"artifact_hash: {receipt.artifact_hash}")
    print(f"checkpoint_id: {receipt.checkpoint_id}")
    print(f"receipt_path: {receipt.receipt_path}")
    print(f"verified: {receipt.verified}")
    print(f"error: {receipt.error}")


def main() -> None:
    parser = argparse.ArgumentParser(prog="think")
    parser.add_argument("--worktree", default=".", help="Worktree path")
    subparsers = parser.add_subparsers(dest="command")

    repo_p = subparsers.add_parser("repo", help="Repository state")
    repo_sub = repo_p.add_subparsers(dest="repo_command")
    repo_inspect = repo_sub.add_parser("inspect", help="Inspect repository")

    box_p = subparsers.add_parser("box", help="Think Box state")
    box_sub = box_p.add_subparsers(dest="box_command")
    box_inspect = box_sub.add_parser("inspect", help="Inspect Think Box")

    job_p = subparsers.add_parser("job", help="Job control")
    job_sub = job_p.add_subparsers(dest="job_command")

    job_create = job_sub.add_parser("create", help="Create a job")
    job_create.add_argument("--job-id", default=None, help="Job ID")
    job_create.add_argument("--intent", required=True, help="Job intent")
    job_create.add_argument("--name", default="", help="Job name")

    job_status = job_sub.add_parser("status", help="Show job status")
    job_status.add_argument("--job-id", required=True)

    job_checkpoint = job_sub.add_parser("checkpoint", help="Checkpoint a job")
    job_checkpoint.add_argument("--job-id", required=True)
    job_checkpoint.add_argument("--name", required=True)

    job_receipt = job_sub.add_parser("receipt", help="Locate job receipt")
    job_receipt.add_argument("--job-id", required=True)

    job_execute = job_sub.add_parser("execute", help="Execute a job on Upstash Box")
    job_execute.add_argument("--job-id", required=True)
    job_execute.add_argument("--exec-command", default="", help="Command to execute")
    job_execute.add_argument("--artifact", default="artifact.json", help="Artifact name")

    job_execute_local = job_sub.add_parser(
        "execute-local",
        help="Execute a bounded command locally (receipt contract; not live remote)",
    )
    job_execute_local.add_argument("--job-id", required=True)
    job_execute_local.add_argument("--exec-command", default="", help="Shell command")
    job_execute_local.add_argument("--artifact", default="artifact.json", help="Artifact name")

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)

    sub_key = getattr(args, f"{args.command}_command", None)
    commands = {
        ("repo", "inspect"): cmd_repo_inspect,
        ("box", "inspect"): cmd_box_inspect,
        ("job", "create"): cmd_job_create,
        ("job", "status"): cmd_job_status,
        ("job", "checkpoint"): cmd_job_checkpoint,
        ("job", "receipt"): cmd_job_receipt,
        ("job", "execute"): cmd_job_execute,
        ("job", "execute-local"): cmd_job_execute_local,
    }
    handler = commands.get((args.command, sub_key))
    if handler is None:
        parser.parse_args([args.command, "--help"])
    try:
        handler(args)
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
