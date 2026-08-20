"""Terminal plugin for kudbEE."""

from __future__ import annotations

import asyncio
from typing import Any

from backend.plugins.base import Tool, ToolResult


class TerminalTool(Tool):
    name = "terminal"
    description = "Execute shell commands"
    permission = "exec"
    requires_approval = True

    async def run(self, args: dict[str, Any], context: dict[str, Any]) -> ToolResult:
        command = args.get("command", "")
        cwd = args.get("cwd", context.get("project_root", "."))
        timeout = int(args.get("timeout", 30))

        if not command:
            return ToolResult(success=False, error="Missing 'command' argument")

        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                cwd=cwd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)

            return ToolResult(
                success=proc.returncode == 0,
                data={
                    "command": command,
                    "stdout": stdout.decode("utf-8", errors="replace"),
                    "stderr": stderr.decode("utf-8", errors="replace"),
                    "return_code": proc.returncode,
                },
            )
        except asyncio.TimeoutError:
            return ToolResult(success=False, error=f"Command timed out after {timeout}s")
        except Exception as e:
            return ToolResult(success=False, error=str(e))
