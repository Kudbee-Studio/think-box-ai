"""Docker plugin for kudbEE."""

from __future__ import annotations

import asyncio
from typing import Any

from backend.plugins.base import Tool, ToolResult


class DockerTool(Tool):
    name = "docker"
    description = "Manage Docker containers and images"
    permission = "exec"
    requires_approval = True

    async def run(self, args: dict[str, Any], context: dict[str, Any]) -> ToolResult:
        action = args.get("action", "ps")
        cwd = args.get("cwd", context.get("project_root", "."))

        commands = {
            "ps": ["docker", "ps", "--format", "{{.Names}}\t{{.Status}}\t{{.Ports}}"],
            "images": ["docker", "images", "--format", "{{.Repository}}:{{.Tag}}\t{{.Size}}"],
            "logs": lambda args: ["docker", "logs", args.get("container", ""), "--tail", "100"],
            "build": lambda args: ["docker", "build", "-t", args.get("tag", "app:latest"), args.get("path", ".")],
            "run": lambda args: ["docker", "run", "--rm", "-d", "-p", args.get("port", "8080:80"), args.get("image", "")],
        }

        cmd = commands.get(action)
        if callable(cmd):
            cmd = cmd(args)
        elif not cmd:
            return ToolResult(success=False, error=f"Unknown docker action: {action}")

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
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
            return ToolResult(success=False, error="Docker command timed out")
        except Exception as e:
            return ToolResult(success=False, error=str(e))
