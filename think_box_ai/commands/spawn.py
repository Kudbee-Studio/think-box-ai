"""Sub-agent spawn commands."""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone

from ..ui.colors import bold, cyan, dim, green, yellow
from ..utils.output import is_json_mode, output_json


def handle_spawn_command(args) -> None:
    sub = args.spawn_command

    if sub == "researcher":
        _spawn_researcher(args)
    elif sub == "runner":
        _spawn_runner(args)
    else:
        print("Usage: thinkbox spawn {researcher|runner}")


def _spawn_researcher(args) -> None:
    agent_id = f"agent_{uuid.uuid4().hex[:8]}"

    if is_json_mode():
        output_json({
            "agent_id": agent_id,
            "type": "researcher",
            "goal": args.goal,
            "status": "spawned",
        })
        return

    print(bold(f"\n  Spawning researcher agent..."))
    print(f"  Agent ID: {cyan(agent_id)}")
    print(f"  Goal: {args.goal}")
    print(dim("  (Simulated — connect to real agent runtime for live execution)"))

    if args.wait:
        print(yellow("  Waiting for completion... (simulated)"))
        print(green(f"  Researcher {agent_id} completed."))


def _spawn_runner(args) -> None:
    agent_id = f"agent_{uuid.uuid4().hex[:8]}"

    if is_json_mode():
        output_json({
            "agent_id": agent_id,
            "type": "runner",
            "goal": args.goal,
            "status": "spawned",
        })
        return

    print(bold(f"\n  Spawning runner agent..."))
    print(f"  Agent ID: {cyan(agent_id)}")
    print(f"  Goal: {args.goal}")
    print(green(f"  Runner {agent_id} spawned."))
