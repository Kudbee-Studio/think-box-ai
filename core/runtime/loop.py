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
            "You are THINK BOX AI, an intelligent research agent that accomplishes goals using tools.\n"
            "Think step by step. Be concise and actionable.\n"
            "Use tools to gather data, then analyze and report findings.\n\n"
            "TOOLS:\n"
            f"{tools_xml}\n\n"
            "To use a tool, output a tool call in this exact format:\n"
            "<tool_call>{\"tool\": \"tool_name\", \"args\": {\"arg1\": \"value1\"}}</tool_call>\n\n"
            "You may output multiple tool calls in one response. After each batch of tool results,\n"
            "decide your next step. When the goal is fully achieved, summarize what you did and\n"
            "write any findings to files using fs_write."
        )

    def _build_tool_results_message(self, results: list[dict[str, Any]]) -> Message:
        content = "Tool results:\n"
        for r in results:
            content += f"\nTool: {r['tool']}\n"
            result_str = json.dumps(r['result'], default=str)[:2000]
            content += f"Result: {result_str}\n"
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
        run_id = str(uuid.uuid8())[:12] if hasattr(uuid, "uuid8") else str(uuid.uuid4())[:12]
        from core.observability import Trace, SpanType, SpanStatus
        trace = Trace(goal=goal, metadata={"run_id": run_id})
        messages: list[Message] = [
            Message(role="system", content=self.system_prompt),
            Message(role="user", content=f"Goal: {goal}"),
        ]

        iterations = 0
        final_output = ""
        tools_used = []
        artifacts = []

        while iterations < self.max_iterations:
            iterations += 1
            logger.info(f"Agent iteration {iterations}", extra={"run_id": run_id})

            model_span = trace.start_span(
                name=f"model_call:{iterations}",
                span_type=SpanType.MODEL_CALL,
                input_data={"messages": len(messages)},
            )
            try:
                response = await self.provider.complete(messages)
                output = response.content or ""
                final_output = output
                trace.end_span(
                    model_span,
                    output={"content": output[:500]},
                    tokens_input=getattr(response, 'tokens_input', 0),
                    tokens_output=getattr(response, 'tokens_output', 0),
                    cost_usd=getattr(response, 'cost_usd', 0.0),
                )
            except Exception as e:
                trace.end_span(model_span, error=str(e), status=SpanStatus.ERROR)
                trace.finish(status="error")
                return {"success": False, "error": str(e), "trace_id": trace.trace_id}

            if self.memory:
                self.memory.append_message("assistant", output)

            tool_calls = self._parse_tool_calls(output)
            if not tool_calls:
                logger.info("No tool calls — goal complete", extra={"run_id": run_id})
                break

            results = []
            for call in tool_calls:
                tool_name = call["tool"]
                tool_args = call.get("args", {})
                tools_used.append(tool_name)
                logger.info(f"Executing tool: {tool_name}", extra={"run_id": run_id})

                tool_span = trace.start_span(
                    name=f"tool:{tool_name}",
                    span_type=SpanType.TOOL_CALL,
                    input_data={"tool": tool_name, "args": tool_args},
                )

                if self.tool_registry and self.tool_registry.has(tool_name):
                    result = await self.tool_registry.execute(tool_name, tool_args)
                    trace.end_span(
                        tool_span,
                        output=result,
                        status=SpanStatus.OK if result.get("success") else SpanStatus.ERROR,
                    )
                    if result.get("success") and result.get("saved_path"):
                        artifacts.append(result["saved_path"])
                else:
                    result = {"error": f"Tool '{tool_name}' not found"}
                    trace.end_span(tool_span, output=result, status=SpanStatus.ERROR)

                results.append({"tool": tool_name, "result": result})

            tool_msg = self._build_tool_results_message(results)
            messages.append(tool_msg)

            if self.memory:
                self.memory.append_message("user", tool_msg.content)

        result = {
            "run_id": run_id,
            "trace_id": trace.trace_id,
            "status": "success",
            "iterations": iterations,
            "output": final_output,
            "tools_used": list(set(tools_used)),
            "artifacts": artifacts,
        }

        if self.memory and hasattr(self.memory, 'store'):
            try:
                self.memory.store.put(
                    key=f"run:{run_id}",
                    layer="task",
                    entry_type="tool_result",
                    value=result,
                )
            except Exception:
                pass

        trace.finish(status="success")
        result.update(trace.get_summary())
        return result
