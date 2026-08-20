"""Core agent loop for kudbEE.

Orchestrates: goal → plan → act → observe → remember → improve.
Emits events to the event bus for real-time UI streaming.
"""

from __future__ import annotations

import asyncio
import json
import uuid
from datetime import datetime, timezone
from typing import Any

from backend.core.event_bus import event_bus
from backend.core.events import EventType
from backend.models.ollama_client import stream_chat
from backend.plugins.registry import plugin_registry


class AgentLoop:
    """The Devin brain — executes goals with streaming, tools, and memory."""

    def __init__(self, session_id: str, model: str = "deepseek-coder:6.7b") -> None:
        self.session_id = session_id
        self.model = model
        self.memory: list[dict[str, Any]] = []
        self.thoughts: list[dict[str, Any]] = []
        self.tools_used: list[str] = []
        self.max_iterations = 20
        self.iteration = 0
        self.task_id = str(uuid.uuid4())[:8]

    async def run(self, goal: str) -> dict[str, Any]:
        """Run the agent loop for a goal.

        Args:
            goal: The goal to execute.

        Returns:
            Result dictionary with status, output, and metadata.
        """
        await event_bus.broadcast_status("running")
        await event_bus.broadcast_thought(f"Starting goal: {goal}", status="info")
        await event_bus.broadcast_task_update(self.task_id, "running", goal)

        try:
            # Phase 1: Planning
            await self._plan(goal)

            # Phase 2: Execution loop
            result = await self._execute(goal)

            # Phase 3: Completion
            await event_bus.broadcast_thought(f"Goal completed successfully", status="success")
            await event_bus.broadcast_task_update(self.task_id, "completed", goal[:100])
            await event_bus.broadcast_status("idle")
            await event_bus.broadcast_memory_update("session", "last_goal", goal)

            return {
                "success": True,
                "result": result,
                "task_id": self.task_id,
                "iterations": self.iteration,
                "tools_used": self.tools_used,
            }

        except Exception as e:
            await event_bus.broadcast_thought(f"Error: {str(e)}", status="error")
            await event_bus.broadcast_task_update(self.task_id, "failed", str(e)[:100])
            await event_bus.broadcast_status("error")
            return {
                "success": False,
                "error": str(e),
                "task_id": self.task_id,
                "iterations": self.iteration,
            }

    async def _plan(self, goal: str) -> None:
        """Plan the execution strategy."""
        await event_bus.broadcast_thought("Analyzing goal and planning execution...", status="thinking")

        tools_desc = ", ".join([t.name for t in plugin_registry.get_enabled()])
        prompt = f"""You are kudbEE, an intelligent agent. Goal: {goal}

Available tools: {tools_desc}

Plan your approach in 1-2 sentences. Be concise."""

        messages = [
            {"role": "system", "content": "You are kudbEE, an intelligent agent OS. Think step by step. Be concise and actionable."},
            {"role": "user", "content": prompt},
        ]

        plan = ""
        async for token in stream_chat(self.model, messages, temperature=0.7, max_tokens=256):
            plan += token
            await event_bus.broadcast_token(token)

        await event_bus.broadcast_thought(f"Plan: {plan[:200]}", status="info")
        self.memory.append({
            "type": "plan",
            "goal": goal,
            "plan": plan,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    async def _execute(self, goal: str) -> str:
        """Execute the goal using tools and reasoning."""
        full_response = ""
        messages = self._build_context(goal)

        async for token in stream_chat(self.model, messages, temperature=0.7, max_tokens=4096):
            full_response += token
            await event_bus.broadcast_token(token)

        # Check if the model wants to use a tool
        tool_call = self._parse_tool_call(full_response)
        if tool_call:
            await self._execute_tool(tool_call)
            # Continue execution with tool result
            return await self._execute(goal)

        return full_response

    async def _execute_tool(self, tool_call: dict[str, Any]) -> None:
        """Execute a tool call and stream results."""
        tool_name = tool_call.get("tool", "")
        tool_args = tool_call.get("args", {})

        await event_bus.broadcast_tool_call(tool_name, tool_args)
        await event_bus.broadcast_thought(f"Executing tool: {tool_name}", status="thinking")

        tool = plugin_registry.get(tool_name)
        if not tool:
            await event_bus.broadcast_tool_result(tool_name, {"success": False, "error": f"Tool not found: {tool_name}"})
            return

        # Check if approval is required
        if tool.requires_approval:
            await event_bus.broadcast_risky_action(
                action_id=str(uuid.uuid4())[:8],
                description=f"Tool {tool_name} requires approval",
                risk_level="medium",
            )
            # In a real implementation, we'd wait for approval here
            # For now, we proceed automatically

        result = await tool.run(tool_args, context={"session_id": self.session_id})

        await event_bus.broadcast_tool_result(tool_name, result.data if result.success else {"error": result.error})
        self.tools_used.append(tool_name)

        status = "success" if result.success else "error"
        await event_bus.broadcast_thought(f"Tool {tool_name} {status}: {str(result.data)[:100]}", status=status)

        self.memory.append({
            "type": "tool_result",
            "tool": tool_name,
            "args": tool_args,
            "result": result.data if result.success else {"error": result.error},
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    def _build_context(self, goal: str) -> list[dict[str, str]]:
        """Build context from memory for the model."""
        messages = [
            {"role": "system", "content": "You are kudbEE, an intelligent agent OS. You help developers accomplish goals by using tools. Think step by step. Be concise and actionable. When you need to use a tool, describe it in JSON format like: {\"tool\": \"tool_name\", \"args\": {...}}"},
        ]

        # Add recent memory
        recent_memory = self.memory[-10:]
        for entry in recent_memory:
            if entry["type"] == "plan":
                messages.append({"role": "assistant", "content": f"[Plan]: {entry['plan']}"})
            elif entry["type"] == "tool_result":
                messages.append({"role": "system", "content": f"[Tool {entry['tool']} result]: {json.dumps(entry['result'])}"})

        messages.append({"role": "user", "content": f"Goal: {goal}"})
        return messages

    def _parse_tool_call(self, text: str) -> dict[str, Any] | None:
        """Parse a tool call from model output."""
        # Look for JSON-like tool calls
        try:
            # Try to find JSON in the response
            start = text.find("{")
            if start != -1:
                end = text.find("}", start) + 1
                if end > start:
                    json_str = text[start:end]
                    data = json.loads(json_str)
                    if isinstance(data, dict) and "tool" in data:
                        return data
        except (json.JSONDecodeError, ValueError):
            pass
        return None


async def run_agent_task(session_id: str, goal: str, model: str) -> dict[str, Any]:
    """Run an agent task and return the result.

    Args:
        session_id: Session identifier.
        goal: Goal to execute.
        model: Model name to use.

    Returns:
        Result dictionary.
    """
    loop = AgentLoop(session_id=session_id, model=model)
    return await loop.run(goal)
