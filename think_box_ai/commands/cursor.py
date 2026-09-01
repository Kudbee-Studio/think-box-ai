"""Cursor SDK integration commands."""

from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone

from ..ui.colors import bold, cyan, dim, green, yellow
from ..utils.output import is_json_mode, output_json


def handle_cursor_command(args) -> None:
    sub = args.cursor_command

    if sub == "run":
        _cursor_run(args)
    elif sub == "list":
        _cursor_list(args)
    elif sub == "logs":
        _cursor_logs(args)
    else:
        print("Usage: thinkbox cursor {run|list|logs}")


def _cursor_run(args) -> None:
    api_key = os.environ.get("CURSOR_API_KEY")
    if not api_key:
        print(yellow("  CURSOR_API_KEY not set."))
        print(dim("  Set it with: export CURSOR_API_KEY=your_key"))
        return

    agent_id = f"cursor_{uuid.uuid4().hex[:8]}"

    if is_json_mode():
        output_json({
            "agent_id": agent_id,
            "runtime": args.runtime,
            "model": args.model,
            "prompt": args.prompt[:100],
            "status": "spawned",
        })
        return

    print(bold(f"\n  Cursor Agent"))
    print(dim("  " + "─" * 40))
    print(f"  Agent ID: {cyan(agent_id)}")
    print(f"  Runtime: {args.runtime}")
    print(f"  Model: {args.model}")
    print(f"  Prompt: {args.prompt[:80]}")
    if args.repo:
        print(f"  Repo: {args.repo}")
    print(dim("\n  (Simulated — requires @cursor/sdk for real execution)"))
    print(green(f"  Agent {agent_id} spawned."))


def _cursor_list(args) -> None:
    runtime = args.runtime

    if is_json_mode():
        output_json({"runtime": runtime, "agents": []})
        return

    print(bold(f"\n  Cursor Agents ({runtime}):"))
    print(dim("  " + "─" * 40))
    print(dim("  No active agents (connect to Cursor SDK for live data)"))


def _cursor_logs(args) -> None:
    agent_id = args.agent_id

    if is_json_mode():
        output_json({"agent_id": agent_id, "logs": []})
        return

    print(bold(f"\n  Agent Logs: {agent_id}"))
    print(dim("  " + "─" * 40))
    print(dim("  No logs available (connect to Cursor SDK for live data)"))
