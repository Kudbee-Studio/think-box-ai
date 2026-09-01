#!/usr/bin/env python3
"""Sub-agent spawning system for Think Box AI.

Spawn child agents that run independently and report back.
Supports: researcher, runner, director, camera, jury hats.
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core.cli_memory import memory
from core.foundation.logging import get_logger

logger = get_logger("spawn")


class SubAgent:
    """A spawned child agent."""

    def __init__(self, hat: str, goal: str, parent_id: str | None = None):
        self.id = f"agent_{uuid.uuid4().hex[:8]}"
        self.hat = hat
        self.goal = goal
        self.parent_id = parent_id
        self.status = "spawning"
        self.result: dict | None = None
        self.created_at = datetime.now(timezone.utc).isoformat()
        self.completed_at: str | None = None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "hat": self.hat,
            "goal": self.goal,
            "parent_id": self.parent_id,
            "status": self.status,
            "result": self.result,
            "created_at": self.created_at,
            "completed_at": self.completed_at,
        }


class AgentSpawner:
    """Spawn and manage sub-agents."""

    def __init__(self):
        self.agents: dict[str, SubAgent] = {}
        self._load()

    def _load(self):
        """Load persisted agents."""
        store = Path("data/subagents.jsonl")
        if store.exists():
            with open(store) as f:
                for line in f:
                    data = json.loads(line.strip())
                    agent = SubAgent(data["hat"], data["goal"], data.get("parent_id"))
                    agent.id = data["id"]
                    agent.status = data["status"]
                    agent.result = data.get("result")
                    agent.created_at = data["created_at"]
                    agent.completed_at = data.get("completed_at")
                    self.agents[agent.id] = agent

    def _save(self, agent: SubAgent):
        """Persist agent state."""
        store = Path("data/subagents.jsonl")
        store.parent.mkdir(parents=True, exist_ok=True)
        with open(store, "a") as f:
            f.write(json.dumps(agent.to_dict()) + "\n")

    async def spawn(self, hat: str, goal: str, parent_id: str | None = None) -> SubAgent:
        """Spawn a new sub-agent."""
        agent = SubAgent(hat, goal, parent_id)
        self.agents[agent.id] = agent
        self._save(agent)

        logger.info(f"Spawned {hat} agent: {agent.id}")
        memory.remember(
            key=f"spawn:{agent.id}",
            value=agent.to_dict(),
            category="context",
            importance=0.8,
        )

        # Execute the agent
        asyncio.create_task(self._execute(agent))

        return agent

    async def _execute(self, agent: SubAgent):
        """Execute the agent's goal."""
        agent.status = "running"
        try:
            # Import here to avoid circular imports
            from core.foundation.bootstrap import bootstrap
            from core.runtime.loop import AgentLoop

            ctx = bootstrap(with_provider=True, with_tools=True)
            loop = AgentLoop(
                provider=ctx.provider,
                tool_registry=ctx.tool_registry,
                max_iterations=20,
            )
            result = await loop.run(agent.goal)

            agent.status = "completed"
            agent.result = result
            agent.completed_at = datetime.now(timezone.utc).isoformat()

            # Store result in memory
            memory.remember(
                key=f"result:{agent.id}",
                value=result,
                category="result",
                importance=1.0,
            )

        except Exception as e:
            agent.status = "failed"
            agent.result = {"error": str(e)}
            agent.completed_at = datetime.now(timezone.utc).isoformat()
            logger.error(f"Agent {agent.id} failed: {e}")

        self._save(agent)

    def get(self, agent_id: str) -> SubAgent | None:
        """Get agent by ID."""
        return self.agents.get(agent_id)

    def list_active(self) -> list[SubAgent]:
        """List all active agents."""
        return [a for a in self.agents.values() if a.status in ("spawning", "running")]

    def list_all(self) -> list[SubAgent]:
        """List all agents."""
        return list(self.agents.values())

    async def wait_for(self, agent_id: str, timeout: float = 300) -> SubAgent | None:
        """Wait for an agent to complete."""
        agent = self.agents.get(agent_id)
        if not agent:
            return None

        start = datetime.now(timezone.utc).timestamp()
        while agent.status in ("spawning", "running"):
            await asyncio.sleep(1)
            if datetime.now(timezone.utc).timestamp() - start > timeout:
                agent.status = "timeout"
                return agent
        return agent


# Global spawner
spawner = AgentSpawner()
