"""Agent loop with tool calling for THINK BOX AI."""

from __future__ import annotations

import json
import re
import uuid
from typing import Any

from core.foundation.logging import get_logger
from core.providers.base import Message

logger = get_logger(__name__)

TOOL_CALL_PATTERN = re.compile(
    r"<tool_call>\s*(\{.*?\})\s*</tool_call>",
    re.DOTALL,
)


class AgentLoop:
    def __init__(
        self,
        provider: Any,
        tool_registry: Any,
        memory: Any = None,
        max_iterations: int = 20,
        system_prompt: str | None = None,
    ) -> None:
        self.provider = provider
        self.tool_registry = tool_registry
        self.memory = memory
        self.max_iterations = max_iterations
        self.system_prompt = system_prompt or self._default_system_prompt()

    def _default_system_prompt(self) -> str:
        tools_xml = self.tool_registry.to_xml() if self.tool_registry else ""
        return (
            "You are THINK BOX AI, an intelligent agent that accomplishes goals using tools.\n"
            "Think step by step. Be concise and actionable.\n\n"
            "TOOLS:\n"
            f"{tools_xml}\n\n"
            "To use a tool, output a tool call in this exact format:\n"
            "<tool_call>{\"tool\": \"tool_name\", \"args\": {\"arg1\": \"value1\"}}</tool_call>\n\n"
            "After each tool result, decide your next step. "
            "When the goal is fully achieved, summarize what you did."
        )

    def _build_tool_results_message(self, results: list[dict[str, Any]]) -> Message:
        content = "Tool results:\n"
        for r in results:
            content += f"\nTool: {r['tool']}\n"
            content += f"Result: {json.dumps(r['result'], default=str)[:2000]}\n"
        return Message(role="user", content=content)

    def _parse_tool_calls(self, text: str) -> list[dict[str, Any]]:
        calls = []
        for match in TOOL_CALL_PATTERN.finditer(text):
            try:
                data = json.loads(match.group(1))
                if "tool" in data:
                    calls.append(data)
            except json.JSONDecodeError:
                continue
        return calls

    async def run(self, goal: str) -> dict[str, Any]:
        messages: list[Message] = [
            Message(role="system", content=self.system_prompt),
            Message(role="user", content=f"Goal: {goal}"),
        ]

        iterations = 0
        final_output = ""

        while iterations < self.max_iterations:
            iterations += 1
            logger.info(f"Agent iteration {iterations}")

            response = await self.provider.complete(messages)
            output = response.content or ""
            final_output = output

            if self.memory:
                self.memory.append_message("assistant", output)

            tool_calls = self._parse_tool_calls(output)
            if not tool_calls:
                logger.info("No tool calls — goal complete")
                break

            results = []
            for call in tool_calls:
                tool_name = call["tool"]
                tool_args = call.get("args", {})
                logger.info(f"Executing tool: {tool_name}")

                if self.tool_registry and self.tool_registry.has(tool_name):
                    result = await self.tool_registry.execute(tool_name, tool_args)
                else:
                    result = {"error": f"Tool '{tool_name}' not found"}

                results.append({"tool": tool_name, "result": result})

            tool_msg = self._build_tool_results_message(results)
            messages.append(tool_msg)

            if self.memory:
                self.memory.append_message("user", tool_msg.content)

        return {
            "status": "success",
            "iterations": iterations,
            "output": final_output,
        }
