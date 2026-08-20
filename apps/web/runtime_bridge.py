#!/usr/bin/env python3
"""
THINK BOX AI — Python Runtime Bridge
Connects the Node.js web backend to the Python agent runtime.
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from core.foundation.bootstrap import bootstrap, shutdown
from core.foundation.config import ThinkBoxConfig
from core.foundation.logging import get_logger
from core.runtime.actor import Actor
from core.runtime.agent import Agent, Goal
from core.runtime.observer import Observer
from core.runtime.planner import Planner

logger = get_logger(__name__)


async def run_agent_loop(goal_statement: str, model: str = "deepseek-coder:6.7b") -> dict:
    """Run the agent loop for a goal.

    Args:
        goal_statement: The goal to execute.
        model: Model name (for logging/config).

    Returns:
        Result dictionary.
    """
    ctx = bootstrap(log_level="WARNING", with_provider=False, with_tools=True)

    try:
        session = ctx.create_session("web-session", "web-agent")
        task_memory = ctx.create_task_memory("web-task", "web-goal", "web-agent")
        config = ThinkBoxConfig(default_model=model)
        agent = Agent(
            agent_id="web-agent",
            session_memory=session,
            task_memory=task_memory,
            config=config,
        )

        goal = Goal(statement=goal_statement, success_criteria=["completed"])

        logger.info("Running goal", extra={"goal": goal_statement, "model": model})

        result = agent.run(
            goal=goal,
            planner=Planner(task_memory=task_memory),
            actor=Actor(
                tool_registry=ctx.tool_registry,
                approval_gate=ctx.approval_gate,
                audit_log=ctx.approval_gate._audit_log if ctx.approval_gate else None,
                memory_store=ctx.store,
            ),
            observer=Observer(),
        )

        return result

    except Exception as e:
        logger.error("Agent loop failed", extra={"error": str(e)})
        return {"status": "failed", "error": str(e)}
    finally:
        shutdown(ctx)


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 runtime_bridge.py '<goal>' [model]")
        sys.exit(1)

    goal = sys.argv[1]
    model = sys.argv[2] if len(sys.argv) > 2 else "deepseek-coder:6.7b"

    result = asyncio.run(run_agent_loop(goal, model))
    print(json.dumps(result))


if __name__ == "__main__":
    main()
