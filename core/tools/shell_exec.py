"""Shell execution tool for THINK BOX AI."""

from __future__ import annotations

import asyncio
import shlex
from typing import Any

from core.tools.registry import ToolDefinition, tool


@tool(
    name="shell_exec",
    description="Execute a shell command",
    permission="exec",
    requires_approval=True,
    input_schema={"type": "object", "properties": {"command": {"type": "string"}, "cwd": {"type": "string"}, "timeout": {"type": "integer"}}, "required": ["command"]},
)
async def shell_exec_async(args: dict[str, Any], context: dict[str, Any] | None = None) -> dict[str, Any]:
    command = args.get("command", "")
    cwd = args.get("cwd", context.get("project_root", ".") if context else ".")
    timeout = int(args.get("timeout", 30))
    if not command:
        return {"success": False, "error": "Missing 'command' argument"}
    try:
        cmd_parts = shlex.split(command)
        proc = await asyncio.create_subprocess_exec(
            *cmd_parts,
            cwd=cwd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        return {
            "success": proc.returncode == 0,
            "stdout": stdout.decode("utf-8", errors="replace"),
            "stderr": stderr.decode("utf-8", errors="replace"),
            "return_code": proc.returncode,
        }
    except asyncio.TimeoutError:
        return {"success": False, "error": f"Command timed out after {timeout}s"}
    except Exception as e:
        return {"success": False, "error": str(e)}


shell_exec = shell_exec_async
shell_exec._tool_definition = ToolDefinition(
    name="shell_exec",
    description="Execute a shell command",
    handler=shell_exec_async,
    permission="exec",
    requires_approval=True,
    input_schema={"type": "object", "properties": {"command": {"type": "string"}, "cwd": {"type": "string"}, "timeout": {"type": "integer"}}, "required": ["command"]},
)
