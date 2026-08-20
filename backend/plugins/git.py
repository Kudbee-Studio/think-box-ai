"""Git plugin for kudbEE."""

from __future__ import annotations

import asyncio
import shlex
from typing import Any

from backend.plugins.base import Tool, ToolResult


class GitTool(Tool):
    name = "git"
    description = "Git operations (status, diff, log, checkout)"
    permission = "read_write"
    requires_approval = True

    async def run(self, args: dict[str, Any], context: dict[str, Any]) -> ToolResult:
        action = args.get("action", "status")
        cwd = args.get("cwd", context.get("project_root", "."))

        commands = {
            "status": "git status -sb",
            "diff": "git diff",
            "log": "git log --oneline -20",
            "branch": "git branch -a",
            "checkout": lambda args: f"git checkout {args.get('branch', '')}",
            "commit": lambda args: f'git commit -am "{args.get("message", "agent commit")}"',
            "add": lambda args: f"git add {args.get('path', '.')}",
        }

        cmd = commands.get(action)
        if callable(cmd):
            cmd = cmd(args)
        elif not cmd:
            return ToolResult(success=False, error=f"Unknown git action: {action}")

        try:
            proc = await asyncio.create_subprocess_shell(
                cmd,
                cwd=cwd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=30)

            return ToolResult(
                success=proc.returncode == 0,
                data={
                    "action": action,
                    "command": cmd,
                    "stdout": stdout.decode("utf-8", errors="replace"),
                    "stderr": stderr.decode("utf-8", errors="replace"),
                    "return_code": proc.returncode,
                },
            )
        except asyncio.TimeoutError:
            return ToolResult(success=False, error="Git command timed out")
        except Exception as e:
            return ToolResult(success=False, error=str(e))
