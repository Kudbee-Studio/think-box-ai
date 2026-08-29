"""Command-line interface for Think Box AI."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import uuid
from typing import Any

from core.execution import LocalExecProvider
from core.memory.store import MemoryStore
from core.runtime.actor import Actor
from core.runtime.planner import Step


EVIDENCE_DIR = os.path.expanduser("~/.local/share/thinkbox/evidence")
DB_PATH = os.path.expanduser("~/.local/share/thinkbox/thinkbox.db")


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


def _get_store() -> MemoryStore:
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    return MemoryStore(DB_PATH)


def _mint_token_for_evidence(store: MemoryStore, think_box_id: str, command: str, ok: bool) -> str | None:
    """Mint a token if exec was successful and token doesn't exist."""
    if not ok:
        return None
    return store.mint_token(box_id=think_box_id, claim=command, author="cli-agent", grounded=True)


def _apply_exec_challenge(store: MemoryStore, token_id: str, ok: bool) -> None:
    """Apply an exec challenge to a token."""
    outcome = 1 if ok else -1
    store.add_challenge(token_id, "exec", outcome)


def _create_actor(think_box_id: str) -> tuple[Actor, MemoryStore]:
    """Create an Actor with LocalExecProvider and persistent evidence."""
    provider = LocalExecProvider()
    store = _get_store()

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
    return Actor(audit_log=audit_log, execution_provider=provider), store


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
        print("error: no command provided", file=sys.stderr)
        return 1

    actor, store = _create_actor(think_box_id)

    step = Step(
        id=f"cli-exec-{uuid.uuid4().hex[:8]}",
        description=command,
        action="execute",
        command=command,
    )
    agent = type("FakeAgent", (), {"agent_id": "cli-agent"})()
    think_box = type("FakeThinkBox", (), {"think_box_id": think_box_id})()

    result = asyncio.run(actor.execute_step(agent, think_box, step))

    if result.get("output"):
        print(result["output"], end="")

    # Mint token for successful exec
    evidence = _load_evidence(think_box_id)
    latest = next(
        (e for e in reversed(evidence) if e.get("action") == "execution_evidence"),
        None,
    )
    if latest and latest.get("metadata", {}).get("ok"):
        token_id = _mint_token_for_evidence(store, think_box_id, command, ok=True)
        if token_id:
            _apply_exec_challenge(store, token_id, ok=True)

    # Return the command's exit code (default 0)
    return result.get("return_code", 0)


def cmd_evidence(args: argparse.Namespace) -> int:
    """Show evidence for a Think Box."""
    think_box_id = args.id
    entries = _load_evidence(think_box_id)

    evidence = [
        e for e in entries
        if e.get("action") == "execution_evidence"
    ]

    if not evidence:
        print(f"no evidence found for {think_box_id}", file=sys.stderr)
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


def cmd_tokens(args: argparse.Namespace) -> int:
    """List tokens for a Think Box."""
    store = _get_store()
    tokens = store.list_tokens(args.id)

    if not tokens:
        print(f"no tokens found for {args.id}", file=sys.stderr)
        return 1

    for token in tokens:
        print(json.dumps({
            "id": token["id"],
            "claim": token["claim"],
            "s": round(token["s"], 4),
            "grounded": bool(token["grounded"]),
            "created_at": token["created_at"],
        }, indent=2))

    return 0


def cmd_token_score(args: argparse.Namespace) -> int:
    """Print token score and last challenge."""
    store = _get_store()
    token = store.get_token(args.token_id)

    if token is None:
        print(f"token not found: {args.token_id}", file=sys.stderr)
        return 1

    challenges = store.list_challenges(args.token_id)
    last = challenges[-1] if challenges else None

    print(json.dumps({
        "id": token["id"],
        "claim": token["claim"],
        "s": round(token["s"], 4),
        "grounded": bool(token["grounded"]),
        "created_at": token["created_at"],
        "last_challenge": {
            "type": last["type"],
            "o": last["o"],
            "w": last["w"],
            "created_at": last["created_at"],
        } if last else None,
    }, indent=2))

    return 0


def cmd_challenge_jury(args: argparse.Namespace) -> int:
    """Run a jury challenge against an LLM endpoint."""
    base_url = args.base_url or os.environ.get("THINKBOX_JURY_URL") or os.environ.get("OPENAI_BASE_URL")

    if not base_url:
        print("error: JURY_UNAVAILABLE — set --base-url, THINKBOX_JURY_URL, or OPENAI_BASE_URL", file=sys.stderr)
        return 2

    store = _get_store()
    token = store.get_token(args.token_id)
    if token is None:
        print(f"token not found: {args.token_id}", file=sys.stderr)
        return 1

    before = token["s"]
    challenge_id = asyncio.run(asyncio.to_thread(store.challenge_jury, args.token_id, base_url))

    if challenge_id is None:
        print("error: jury challenge failed (timeout, error, or non-YES/NO reply)", file=sys.stderr)
        return 1

    token = store.get_token(args.token_id)
    print(json.dumps({
        "challenge_id": challenge_id,
        "before": round(before, 4),
        "after": round(token["s"], 4),
        "delta": round(token["s"] - before, 4),
    }, indent=2))
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    """List all Think Boxes with evidence."""
    store = _get_store()
    conn = store._get_conn()
    rows = conn.execute(
        "SELECT DISTINCT box_id FROM think_tokens ORDER BY box_id"
    ).fetchall()

    if not rows:
        print("no think boxes found", file=sys.stderr)
        return 1

    for row in rows:
        box_id = row["box_id"]
        tokens = store.list_tokens(box_id)
        print(f"{box_id}  tokens={len(tokens)}")

    return 0


def cmd_status(args: argparse.Namespace) -> int:
    """Show detailed status for a Think Box."""
    store = _get_store()
    tokens = store.list_tokens(args.id)

    if not tokens:
        print(f"no tokens found for {args.id}", file=sys.stderr)
        return 1

    total_score = sum(t["s"] for t in tokens)
    grounded = sum(1 for t in tokens if t["grounded"])

    print(json.dumps({
        "box_id": args.id,
        "token_count": len(tokens),
        "total_score": round(total_score, 4),
        "avg_score": round(total_score / len(tokens), 4),
        "grounded": grounded,
        "tokens": [
            {
                "id": t["id"],
                "claim": t["claim"],
                "s": round(t["s"], 4),
                "grounded": bool(t["grounded"]),
            }
            for t in tokens
        ],
    }, indent=2))
    return 0


def cmd_clear_cache(args: argparse.Namespace) -> int:
    """Clear the provider snapshot cache."""
    cache_path = os.path.expanduser("~/.local/share/thinkbox/snapshot_cache.db")
    if os.path.exists(cache_path):
        os.remove(cache_path)
        print("snapshot cache cleared")
    else:
        print("no snapshot cache found")
    return 0


def cmd_challenge_human(args: argparse.Namespace) -> int:
    """Apply a human challenge (manual scoring)."""
    store = _get_store()
    token = store.get_token(args.token_id)
    if token is None:
        print(f"token not found: {args.token_id}", file=sys.stderr)
        return 1

    outcome_map = {"pass": 1, "fail": -1, "neutral": 0}
    outcome = outcome_map.get(args.verdict)
    if outcome is None:
        print(f"error: invalid verdict '{args.verdict}'. Use: pass, fail, neutral", file=sys.stderr)
        return 1

    before = token["s"]
    challenge_id = store.add_challenge(args.token_id, "human", outcome)

    if challenge_id is None:
        print("error: challenge failed", file=sys.stderr)
        return 1

    token = store.get_token(args.token_id)
    print(json.dumps({
        "challenge_id": challenge_id,
        "verdict": args.verdict,
        "before": round(before, 4),
        "after": round(token["s"], 4),
        "delta": round(token["s"] - before, 4),
    }, indent=2))
    return 0


def cmd_challenge_replay(args: argparse.Namespace) -> int:
    """Replay the most recent challenge for a token."""
    store = _get_store()
    token = store.get_token(args.token_id)
    if token is None:
        print(f"token not found: {args.token_id}", file=sys.stderr)
        return 1

    before = token["s"]
    challenge_id = store.challenge_replay(args.token_id)

    if challenge_id is None:
        print("error: no prior challenge to replay", file=sys.stderr)
        return 1

    token = store.get_token(args.token_id)
    print(json.dumps({
        "challenge_id": challenge_id,
        "type": "replay",
        "before": round(before, 4),
        "after": round(token["s"], 4),
        "delta": round(token["s"] - before, 4),
    }, indent=2))
    return 0


def cmd_export(args: argparse.Namespace) -> int:
    """Export a Think Box to stdout or a file."""
    store = _get_store()
    try:
        data = store.export_box(args.id)
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1

    output = json.dumps(data, indent=2)
    if args.output:
        with open(args.output, "w") as f:
            f.write(output)
        print(f"exported to {args.output}")
    else:
        print(output)
    return 0


def cmd_import(args: argparse.Namespace) -> int:
    """Import a Think Box from a JSON file."""
    store = _get_store()
    try:
        with open(args.file) as f:
            data = json.load(f)
        box_id = store.import_box(data)
    except (FileNotFoundError, json.JSONDecodeError, ValueError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1

    print(f"imported box: {box_id}")
    return 0


def cmd_delete(args: argparse.Namespace) -> int:
    """Delete a Think Box and all its tokens/challenges."""
    store = _get_store()
    if not store.delete_box(args.id):
        print(f"error: box not found or invalid: {args.id}", file=sys.stderr)
        return 1

    # Also try to delete evidence file
    evidence_file = _evidence_file(args.id)
    if os.path.exists(evidence_file):
        os.remove(evidence_file)

    print(f"deleted box: {args.id}")
    return 0


def cmd_leaderboard(args: argparse.Namespace) -> int:
    """Show top-scoring tokens across all boxes."""
    store = _get_store()
    conn = store._get_conn()
    rows = conn.execute(
        "SELECT id, box_id, claim, s, grounded FROM think_tokens ORDER BY s DESC LIMIT ?",
        (args.limit,),
    ).fetchall()

    if not rows:
        print("no tokens found", file=sys.stderr)
        return 1

    print(json.dumps([
        {
            "id": row["id"],
            "box_id": row["box_id"],
            "claim": row["claim"],
            "s": round(row["s"], 4),
            "grounded": bool(row["grounded"]),
        }
        for row in rows
    ], indent=2))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="thinkbox",
        description="Think Box AI — create, exec, evidence, tokens, jury",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__import__('think_box_ai').__version__}")
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

    # thinkbox tokens <id>
    p_tokens = subparsers.add_parser("tokens", help="List tokens for a Think Box")
    p_tokens.add_argument("id", help="Think Box ID")
    p_tokens.set_defaults(func=cmd_tokens)

    # thinkbox token-score <tid>
    p_score = subparsers.add_parser("token-score", help="Print token score and last challenge")
    p_score.add_argument("token_id", help="Token ID")
    p_score.set_defaults(func=cmd_token_score)

    # thinkbox challenge-jury <tid> [--base-url URL]
    p_jury = subparsers.add_parser("challenge-jury", help="Run a jury challenge against an LLM")
    p_jury.add_argument("token_id", help="Token ID")
    p_jury.add_argument("--base-url", default=None, help="LLM endpoint base URL")
    p_jury.set_defaults(func=cmd_challenge_jury)

    # thinkbox list
    p_list = subparsers.add_parser("list", help="List all Think Boxes with tokens")
    p_list.set_defaults(func=cmd_list)

    # thinkbox status <id>
    p_status = subparsers.add_parser("status", help="Show Think Box status")
    p_status.add_argument("id", help="Think Box ID")
    p_status.set_defaults(func=cmd_status)

    # thinkbox clear-cache
    p_clear = subparsers.add_parser("clear-cache", help="Clear provider snapshot cache")
    p_clear.set_defaults(func=cmd_clear_cache)

    # thinkbox challenge-human <tid> <verdict>
    p_human = subparsers.add_parser("challenge-human", help="Apply a human challenge (pass/fail/neutral)")
    p_human.add_argument("token_id", help="Token ID")
    p_human.add_argument("verdict", choices=["pass", "fail", "neutral"], help="Human verdict")
    p_human.set_defaults(func=cmd_challenge_human)

    # thinkbox challenge-replay <tid>
    p_replay = subparsers.add_parser("challenge-replay", help="Replay the most recent challenge")
    p_replay.add_argument("token_id", help="Token ID")
    p_replay.set_defaults(func=cmd_challenge_replay)

    # thinkbox export <id> [-o FILE]
    p_export = subparsers.add_parser("export", help="Export a Think Box")
    p_export.add_argument("id", help="Think Box ID")
    p_export.add_argument("-o", "--output", help="Output file (default: stdout)")
    p_export.set_defaults(func=cmd_export)

    # thinkbox import <file>
    p_import = subparsers.add_parser("import", help="Import a Think Box from JSON")
    p_import.add_argument("file", help="JSON file to import")
    p_import.set_defaults(func=cmd_import)

    # thinkbox delete <id>
    p_delete = subparsers.add_parser("delete", help="Delete a Think Box")
    p_delete.add_argument("id", help="Think Box ID")
    p_delete.set_defaults(func=cmd_delete)

    # thinkbox leaderboard [limit]
    p_lb = subparsers.add_parser("leaderboard", help="Show top-scoring tokens")
    p_lb.add_argument("--limit", type=int, default=10, help="Number of tokens to show")
    p_lb.set_defaults(func=cmd_leaderboard)

    args = parser.parse_args()

    # Strip the "--" from argv if present
    if hasattr(args, "argv") and args.argv and args.argv[0] == "--":
        args.argv = args.argv[1:]

    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
