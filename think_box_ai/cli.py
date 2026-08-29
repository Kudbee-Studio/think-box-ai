"""Command-line interface for Think Box AI."""

from __future__ import annotations

import argparse
import json
import os
import sys
import uuid

from think_box_ai import __version__
from think_box_ai.token import SYMBOL


def _get_db_path() -> str:
    """Get DB path from environment or default."""
    return os.environ.get("THINKBOX_DB_PATH", os.path.expanduser("~/.local/share/thinkbox/thinkbox.db"))


def _get_evidence_dir() -> str:
    """Get evidence dir from environment or default."""
    return os.environ.get("THINKBOX_EVIDENCE_DIR", os.path.expanduser("~/.local/share/thinkbox/evidence"))


def _ensure_evidence_dir() -> None:
    os.makedirs(_get_evidence_dir(), exist_ok=True)


def _evidence_file(think_box_id: str) -> str:
    return os.path.join(_get_evidence_dir(), f"{think_box_id}.jsonl")


def _append_evidence(think_box_id: str, entry: dict) -> None:
    _ensure_evidence_dir()
    with open(_evidence_file(think_box_id), "a") as f:
        f.write(json.dumps(entry) + "\n")


def _load_evidence(think_box_id: str) -> list[dict]:
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


def _get_store():
    os.makedirs(os.path.dirname(_get_db_path()), exist_ok=True)
    from core.memory.store import MemoryStore
    return MemoryStore(_get_db_path())


def cmd_create(args: argparse.Namespace) -> int:
    """Create a new Think Box."""
    think_box_id = f"tb-{uuid.uuid4().hex[:12]}"
    goal = " ".join(args.goal) if args.goal else ""
    store = _get_store()
    store.save_box(think_box_id, goal=goal, state="created")
    print(think_box_id)
    return 0


def cmd_exec(args: argparse.Namespace) -> int:
    """Execute a command in a Think Box."""
    think_box_id = args.id
    command = " ".join(args.argv)
    if not command:
        print("error: no command provided", file=sys.stderr)
        return 1

    import asyncio
    from core.tools import shell_exec

    store = _get_store()
    box = store.get_box(think_box_id)
    if box is None:
        print(f"error: think box not found: {think_box_id}", file=sys.stderr)
        return 1

    store.update_box_state(think_box_id, "executing")

    result = asyncio.run(shell_exec({"command": command}))
    execution_ok = result.get("success", False)

    if execution_ok:
        if result.get("stdout"):
            print(result["stdout"], end="")
        token_id = _mint_token_for_evidence(store, think_box_id, command, ok=True)
        if token_id:
            _apply_exec_challenge(store, token_id, ok=True)
        store.update_box_state(think_box_id, "complete")
    else:
        store.update_box_state(think_box_id, "failed")
        print(f"error: {result.get('error', 'unknown error')}", file=sys.stderr)
        return 1

    return 0


def _mint_token_for_evidence(store, think_box_id: str, command: str, ok: bool) -> str | None:
    if not ok:
        return None
    return store.mint_token(box_id=think_box_id, claim=command, author="cli-agent", grounded=True)


def _apply_exec_challenge(store, token_id: str, ok: bool) -> None:
    outcome = 1 if ok else -1
    store.add_challenge(token_id, "exec", outcome)


def cmd_evidence(args: argparse.Namespace) -> int:
    """Show evidence for a Think Box."""
    think_box_id = args.id
    entries = _load_evidence(think_box_id)
    evidence = [e for e in entries if e.get("action") == "execution_evidence"]
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
        "last_challenge": {
            "type": last["type"],
            "o": last["o"],
        } if last else None,
    }, indent=2))
    return 0


def cmd_challenge_jury(args: argparse.Namespace) -> int:
    """Run a jury challenge."""
    base_url = args.base_url or os.environ.get("THINKBOX_JURY_URL") or os.environ.get("OPENAI_BASE_URL")
    if not base_url:
        print("error: JURY_UNAVAILABLE — set --base-url, THINKBOX_JURY_URL, or OPENAI_BASE_URL", file=sys.stderr)
        return 2
    store = _get_store()
    token = store.get_token(args.token_id)
    if token is None:
        print(f"token not found: {args.token_id}", file=sys.stderr)
        return 1
    challenge_id = __import__('asyncio').run(__import__('asyncio').to_thread(store.challenge_jury, args.token_id, base_url))
    if challenge_id is None:
        print("error: jury challenge failed", file=sys.stderr)
        return 1
    token = store.get_token(args.token_id)
    print(json.dumps({"challenge_id": challenge_id, "s": round(token["s"], 4)}, indent=2))
    return 0


def cmd_challenge_human(args: argparse.Namespace) -> int:
    """Apply a human challenge."""
    store = _get_store()
    outcome_map = {"pass": 1, "fail": -1, "neutral": 0}
    outcome = outcome_map.get(args.verdict)
    if outcome is None:
        print(f"error: invalid verdict '{args.verdict}'", file=sys.stderr)
        return 1
    challenge_id = store.add_challenge(args.token_id, "human", outcome)
    if challenge_id is None:
        print("error: challenge failed", file=sys.stderr)
        return 1
    print(json.dumps({"challenge_id": challenge_id, "verdict": args.verdict}, indent=2))
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    """List all Think Boxes."""
    store = _get_store()
    conn = store._get_conn()
    rows = conn.execute("SELECT DISTINCT box_id FROM think_tokens ORDER BY box_id").fetchall()
    if not rows:
        print("no think boxes found", file=sys.stderr)
        return 1
    for row in rows:
        print(row["box_id"])
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    """Show Think Box status."""
    store = _get_store()
    tokens = store.list_tokens(args.id)
    if not tokens:
        print(f"no tokens found for {args.id}", file=sys.stderr)
        return 1
    total_score = sum(t["s"] for t in tokens)
    print(json.dumps({
        "box_id": args.id,
        "token_count": len(tokens),
        "avg_score": round(total_score / len(tokens), 4),
    }, indent=2))
    return 0


def cmd_chat(args: argparse.Namespace) -> int:
    """Stream chat from LLM."""
    from core.providers import OpenAICompatProvider
    from core.providers.base import Message

    base_url = args.base_url or os.environ.get("OPENAI_BASE_URL") or "https://api.openai.com/v1"
    model = args.model or os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
    api_key = args.api_key or os.environ.get("OPENAI_API_KEY", "")

    provider = OpenAICompatProvider({"base_url": base_url, "model": model, "api_key": api_key})
    messages = [Message(role="user", content=" ".join(args.message))]

    import asyncio
    async def _stream():
        async for token in provider.stream(messages):
            sys.stdout.write(token)
            sys.stdout.flush()

    try:
        asyncio.run(_stream())
        print()
        return 0
    except Exception as e:
        print(f"error: {e}", file=sys.stderr)
        return 1


def cmd_agent(args: argparse.Namespace) -> int:
    """Run a full agent demo: create → exec → token → challenge → result."""
    goal = " ".join(args.goal)
    if not goal:
        print("error: no goal provided", file=sys.stderr)
        return 1

    WIDTH = 50
    def line(char: str = "─") -> None:
        print(char * WIDTH)
    def header(text: str) -> None:
        print()
        print(f"  {text}")
        line()

    header("KUDBEE")
    print(f"  Goal: {goal}")
    line()

    # Step 1: Create Think Box
    think_box_id = f"tb-{uuid.uuid4().hex[:12]}"
    store = _get_store()
    store.save_box(think_box_id, goal=goal, state="created")
    print(f"  Think Box: {think_box_id}")

    # Step 2: Execute command
    import asyncio
    from core.tools import shell_exec

    result = asyncio.run(shell_exec({"command": goal}))
    execution_ok = result.get("success", False)
    print(f"  Execution: {'✓' if execution_ok else '✗'}")
    if result.get("stdout"):
        print(f"  Output: {result['stdout'].strip()[:100]}")

    # Step 3: Mint token
    token_id = None
    if execution_ok:
        token_id = store.mint_token(box_id=think_box_id, claim=goal[:200], author="kudbee-agent", grounded=True)
        if token_id:
            store.add_challenge(token_id, "exec", outcome=1)
    print(f"  Think Token: {token_id or 'none'}")

    # Step 4: Provider info
    llm_provider = os.environ.get("OPENAI_BASE_URL", "local")
    llm_model = os.environ.get("OPENAI_MODEL", "mercury-2")
    print(f"  Provider: {llm_model} ({llm_provider})")

    # Step 5: Challenge
    if token_id:
        challenges = store.list_challenges(token_id)
        print(f"  Challenges: {len(challenges)} ✓")

    # Step 6: Score
    if token_id:
        token = store.get_token(token_id)
        print(f"  Confidence: s={round(token['s'], 4)}")

    # Step 7: Result
    line("═")
    print(f"  Result:")
    if result.get("stdout"):
        for rline in result["stdout"].strip().split("\n")[:5]:
            print(f"    {rline}")
    line("═")

    store.update_box_state(think_box_id, "complete" if execution_ok else "failed")
    return 0 if execution_ok else 1


def cmd_health(args: argparse.Namespace) -> int:
    """Run health checks and display results."""
    from core.foundation.health import full_health_check

    db_path = _get_db_path()
    report = full_health_check(db_path if os.path.exists(db_path) else None)
    print(json.dumps(report, indent=2))
    return 0 if report["status"] == "ok" else 1


def cmd_connect(args: argparse.Namespace) -> int:
    """Human-in-the-loop verification gate for approving operations."""
    store = _get_store()

    if args.action == "list":
        boxes = store.list_boxes()
        pending = [b for b in boxes if b.get("state") == "awaiting_approval"]
        if not pending:
            print("No pending approvals")
            return 0
        for b in pending:
            print(json.dumps({"id": b["id"], "goal": b.get("goal", ""), "state": b["state"]}, indent=2))
        return 0

    if args.action == "approve":
        store.update_box_state(args.id, "approved")
        print(json.dumps({"id": args.id, "state": "approved"}))
        return 0

    if args.action == "reject":
        store.update_box_state(args.id, "rejected")
        print(json.dumps({"id": args.id, "state": "rejected"}))
        return 0

    if args.action == "request":
        box_id = f"tb-{uuid.uuid4().hex[:12]}"
        store.save_box(box_id, goal=args.description, state="awaiting_approval")
        print(json.dumps({"id": box_id, "state": "awaiting_approval", "description": args.description}, indent=2))
        return 0

    if args.action == "grant":
        return cmd_connect_grant(args)

    return 1


def cmd_connect_grant(args: argparse.Namespace) -> int:
    """Generate grant application packet for NVIDIA Inception or AWS Activate."""
    store = _get_store()

    if args.grant_type == "nvidia":
        packet = {
            "program": "NVIDIA Inception",
            "status": "draft",
            "benefits": {
                "dgx_cloud_credits": "$100,000",
                "aws_credits": "$100,000",
                "nebius_credits": "$150,000",
                "hardware_pricing": "Preferred GPU rebate",
                "training": "Free DLI courses",
            },
            "requirements": [
                "At least one employed developer",
                "Working website",
                "Officially incorporated (< 10 years)",
                "Not a consultancy/crypto/cloud reseller",
            ],
            "application_url": "https://programs.nvidia.com/phoenix/application",
            "timeline": "1-4 weeks review",
            "next_steps": [
                "Submit company profile + pitch deck",
                "Use business email (not Gmail)",
                "Wait for approval",
                "Request credits separately after approval",
            ],
        }
    elif args.grant_type == "aws":
        packet = {
            "program": "AWS Activate",
            "status": "draft",
            "tiers": {
                "founders": {"credits": "$1,000-$5,000", "timeline": "1-3 days"},
                "portfolio": {"credits": "up to $200,000", "timeline": "1-2 weeks"},
            },
            "requirements": [
                "Corporate email (domain-matched)",
                "Paid-tier AWS account",
                "Live website",
                "Pre-Series B, <10 years old",
            ],
            "application_url": "https://aws.amazon.com/activate/",
            "next_steps": [
                "Create AWS Builder ID",
                "Complete Activate profile",
                "Link AWS account",
                "Submit application",
            ],
        }
    else:
        print(f"error: unknown grant type '{args.grant_type}'", file=sys.stderr)
        return 1

    box_id = f"tb-{uuid.uuid4().hex[:12]}"
    store.save_box(box_id, goal=f"Grant: {args.grant_type}", state="grant_pending")
    print(json.dumps(packet, indent=2))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="kudbee",
        description="KUDBEE Think Box CLI",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument("--info", action="store_true", help="Show token info")
    subparsers = parser.add_subparsers(dest="command", required=True)

    p_create = subparsers.add_parser("create", help="Create a new Think Box")
    p_create.add_argument("--goal", nargs="*", default=[], help="Goal statement")
    p_create.set_defaults(func=cmd_create)

    p_exec = subparsers.add_parser("exec", help="Execute command in Think Box")
    p_exec.add_argument("id", help="Think Box ID")
    p_exec.add_argument("argv", nargs=argparse.REMAINDER, help="Command and arguments")
    p_exec.set_defaults(func=cmd_exec)

    p_evidence = subparsers.add_parser("evidence", help="Show evidence")
    p_evidence.add_argument("id", help="Think Box ID")
    p_evidence.set_defaults(func=cmd_evidence)

    p_tokens = subparsers.add_parser("tokens", help="List tokens")
    p_tokens.add_argument("id", help="Think Box ID")
    p_tokens.set_defaults(func=cmd_tokens)

    p_score = subparsers.add_parser("token-score", help="Token score")
    p_score.add_argument("token_id", help="Token ID")
    p_score.set_defaults(func=cmd_token_score)

    p_jury = subparsers.add_parser("challenge-jury", help="LLM jury challenge")
    p_jury.add_argument("token_id", help="Token ID")
    p_jury.add_argument("--base-url", default=None, help="LLM endpoint")
    p_jury.set_defaults(func=cmd_challenge_jury)

    p_human = subparsers.add_parser("challenge-human", help="Manual scoring")
    p_human.add_argument("token_id", help="Token ID")
    p_human.add_argument("verdict", choices=["pass", "fail", "neutral"])
    p_human.set_defaults(func=cmd_challenge_human)

    p_chat = subparsers.add_parser("chat", help="Stream chat from LLM")
    p_chat.add_argument("message", nargs="+", help="Message to send")
    p_chat.add_argument("--model", help="Model name")
    p_chat.add_argument("--base-url", help="API base URL")
    p_chat.add_argument("--api-key", help="API key")
    p_chat.set_defaults(func=cmd_chat)

    p_agent = subparsers.add_parser("agent", help="Run full agent demo")
    p_agent.add_argument("goal", nargs="+", help="Goal/command to execute")
    p_agent.set_defaults(func=cmd_agent)

    p_health = subparsers.add_parser("health", help="Run health checks")
    p_health.set_defaults(func=cmd_health)

    p_list = subparsers.add_parser("list", help="List all Think Boxes")
    p_list.set_defaults(func=cmd_list)

    p_status = subparsers.add_parser("status", help="Box status")
    p_status.add_argument("id", help="Think Box ID")
    p_status.set_defaults(func=cmd_status)

    p_connect = subparsers.add_parser("connect", help="Human-in-the-loop verification")
    p_connect.add_argument("action", choices=["list", "approve", "reject", "request", "grant"], help="Action")
    p_connect.add_argument("--id", help="Box ID for approve/reject")
    p_connect.add_argument("--description", help="Description for request")
    p_connect.add_argument("--grant-type", choices=["nvidia", "aws"], help="Grant type for grant action")
    p_connect.set_defaults(func=cmd_connect)

    args = parser.parse_args()

    if args.info:
        print(f"Token symbol : {SYMBOL}")
        print(f"Version      : {__version__}")
        return 0
    elif hasattr(args, 'func'):
        return args.func(args)
    else:
        parser.print_help()
        return 0


if __name__ == "__main__":
    main()
