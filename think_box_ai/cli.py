"""Command-line interface for Think Box AI."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import uuid
from typing import Any

from core.execution import LocalExecProvider
from core.governance.audit import AuditLog
from core.runtime.actor import Actor
from core.runtime.planner import Step


EVIDENCE_DIR = os.path.expanduser("~/.local/share/thinkbox/evidence")


def _ensure_evidence_dir() -> None:
    os.makedirs(EVIDENCE_DIR, exist_ok=True)


def _evidence_file(think_box_id: str) -> str:
    return os.path.join(EVIDENCE_DIR, f"{think_box_id}.jsonl")


def _append_evidence(think_box_id: str, entry: dict[str, Any]) -> None:
    _ensure_evidence_dir()
    with open(_evidence_file(think_box_id), "a") as f:
        f.write(json.dumps(entry) + "\n")


def _load_evidence(think_box_id: str) -> list[dict[str, Any]]:
    path = _evidence_file(think_box_id)
    if not os.path.exists(path):
        return []
    entries = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return entries


def _create_actor(think_box_id: str) -> Actor:
    """Create an Actor with LocalExecProvider and persistent evidence."""
    provider = LocalExecProvider()

    class PersistentAuditLog:
        def record(self, action: str, actor: str, outcome: str, metadata: dict | None = None) -> None:
            _append_evidence(think_box_id, {
                "action": action,
                "actor": actor,
                "outcome": outcome,
                "metadata": metadata or {},
            })

        def list_entries(self) -> list[dict]:
            return _load_evidence(think_box_id)

    audit_log = PersistentAuditLog()
    return Actor(audit_log=audit_log, execution_provider=provider)


def cmd_create(args: argparse.Namespace) -> int:
    """Create a new Think Box and print its ID."""
    think_box_id = f"tb-{uuid.uuid4().hex[:12]}"
    print(think_box_id)
    return 0


def cmd_exec(args: argparse.Namespace) -> int:
    """Execute a command in a Think Box."""
    think_box_id = args.id
    command = " ".join(args.argv)

    if not command:
        print("error: no command provided", file=__import__("sys").stderr)
        return 1

    actor = _create_actor(think_box_id)

    step = Step(
        id=f"cli-exec-{uuid.uuid4().hex[:8]}",
        description=command,
        action="execute",
        command=command,
    )
    agent = type("FakeAgent", (), {"agent_id": "cli-agent"})()
    think_box = type("FakeThinkBox", (), {"think_box_id": think_box_id})()

    result = asyncio.run(actor.execute_step(agent, think_box, step))

    if result.get("status") == "error":
        print(f"error: {result.get('error', 'unknown error')}", file=__import__("sys").stderr)
        return 1

    if result.get("output"):
        print(result["output"], end="")
    return 0


def cmd_evidence(args: argparse.Namespace) -> int:
    """Show evidence for a Think Box."""
    think_box_id = args.id
    entries = _load_evidence(think_box_id)

    evidence = [
        e for e in entries
        if e.get("action") == "execution_evidence"
    ]

    if not evidence:
        print(f"no evidence found for {think_box_id}", file=__import__("sys").stderr)
        return 1

    for entry in evidence:
        meta = entry.get("metadata", {})
        print(json.dumps({
            "action": entry.get("action"),
            "outcome": entry.get("outcome"),
            "provider": meta.get("provider"),
            "exit_code": meta.get("exit_code"),
            "ok": meta.get("ok"),
            "think_box_id": meta.get("think_box_id"),
            "step_id": meta.get("step_id"),
            "started_at": meta.get("started_at"),
            "finished_at": meta.get("finished_at"),
        }, indent=2))

    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="thinkbox",
        description="Think Box AI — create, exec, evidence",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # thinkbox create
    p_create = subparsers.add_parser("create", help="Create a new Think Box")
    p_create.set_defaults(func=cmd_create)

    # thinkbox exec <id> -- <argv>
    p_exec = subparsers.add_parser("exec", help="Execute a command in a Think Box")
    p_exec.add_argument("id", help="Think Box ID")
    p_exec.add_argument("argv", nargs=argparse.REMAINDER, help="Command and arguments")
    p_exec.set_defaults(func=cmd_exec)

    # thinkbox evidence <id>
    p_evidence = subparsers.add_parser("evidence", help="Show evidence for a Think Box")
    p_evidence.add_argument("id", help="Think Box ID")
    p_evidence.set_defaults(func=cmd_evidence)

    args = parser.parse_args()

    # Strip the "--" from argv if present
    if hasattr(args, "argv") and args.argv and args.argv[0] == "--":
        args.argv = args.argv[1:]

    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
