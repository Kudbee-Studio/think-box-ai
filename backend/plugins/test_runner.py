"""Test runner plugin for kudbEE."""

from __future__ import annotations

import asyncio
from typing import Any

from backend.plugins.base import Tool, ToolResult


class TestRunnerTool(Tool):
    name = "test_runner"
    description = "Run tests in the project"
    permission = "exec"
    requires_approval = True

    async def run(self, args: dict[str, Any], context: dict[str, Any]) -> ToolResult:
        cwd = args.get("cwd", context.get("project_root", "."))
        test_path = args.get("path", "tests")
        timeout = int(args.get("timeout", 60))

        commands = {
            "pytest": ["python3", "-m", "pytest", test_path, "-v", "--tb=short"],
            "unittest": ["python3", "-m", "unittest", "discover", "-s", test_path, "-v"],
            "npm": ["npm", "test"],
            "jest": ["npx", "jest", test_path, "--colors"],
        }

        framework = args.get("framework", "pytest")
        cmd = commands.get(framework, commands["pytest"])

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=cwd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)

            return ToolResult(
                success=proc.returncode == 0,
                data={
                    "framework": framework,
                    "command": cmd,
                    "stdout": stdout.decode("utf-8", errors="replace"),
                    "stderr": stderr.decode("utf-8", errors="replace"),
                    "return_code": proc.returncode,
                },
            )
        except asyncio.TimeoutError:
            return ToolResult(success=False, error=f"Tests timed out after {timeout}s")
        except Exception as e:
            return ToolResult(success=False, error=str(e))
