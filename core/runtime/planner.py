"""Planner for THINK BOX AI."""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from typing import Any

from core.providers.base import Message


@dataclass
class Step:
    id: str
    description: str
    action: str
    expected_output: dict[str, Any] | None = None
    parameters: dict[str, Any] = field(default_factory=dict)


class Planner:
    def __init__(self, task_memory: Any = None, provider: Any = None) -> None:
        self.task_memory = task_memory
        self.provider = provider

    def plan(self, think_box: Any) -> list[Step]:
        goal = getattr(think_box, "goal", None)
        statement = goal.statement if goal else "unknown goal"

        if self.provider is not None:
            try:
                asyncio.get_running_loop()
            except RuntimeError:
                return asyncio.run(self._plan_with_provider(statement))

        return [self._placeholder_step(statement)]

    async def _plan_with_provider(self, statement: str) -> list[Step]:
        system_prompt = (
            "You are a planning assistant. Break down the goal into actionable steps. "
            "Return a JSON array of steps, each with 'id', 'description', 'action', and optionally 'parameters'. "
            "Example: [{\"id\": \"step-1\", \"description\": \"Read the file\", \"action\": \"file_read\", \"parameters\": {\"path\": \"/tmp/file.txt\"}}]"
        )
        messages = [
            Message(role="system", content=system_prompt),
            Message(role="user", content=f"Goal: {statement}"),
        ]
        try:
            response = await self.provider.complete(messages)
            content = response.content.strip()
            steps = self._parse_response(content)
            if steps:
                return steps
        except Exception:
            pass
        return [self._placeholder_step(statement)]

    def _parse_response(self, content: str) -> list[Step]:
        start = content.find("[")
        end = content.rfind("]")
        if start != -1 and end != -1 and end > start:
            try:
                data = json.loads(content[start : end + 1])
                steps = []
                for item in data:
                    if isinstance(item, dict) and "description" in item and "action" in item:
                        steps.append(
                            Step(
                                id=item.get("id", f"step-{len(steps) + 1}"),
                                description=item["description"],
                                action=item["action"],
                                expected_output=item.get("expected_output"),
                                parameters=item.get("parameters", {}),
                            )
                        )
                return steps
            except json.JSONDecodeError:
                pass

        steps = []
        for i, line in enumerate(content.splitlines()):
            line = line.strip()
            if not line:
                continue
            steps.append(Step(id=f"step-{i + 1}", description=line, action="execute"))
        return steps

    def _placeholder_step(self, statement: str) -> Step:
        return Step(
            id="step-1",
            description=f"Analyze and execute: {statement}",
            action="execute",
            expected_output={"status": "success"},
        )
