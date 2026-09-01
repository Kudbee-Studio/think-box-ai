"""Shell execution tool for THINK BOX AI.

Provides sandboxed shell execution with command whitelisting,
path validation, and resource limits.
"""

from __future__ import annotations

import asyncio
import os
import shlex
from typing import Any

from core.tools.registry import ToolDefinition, tool

ALLOWED_COMMANDS = {
    "ls", "cat", "head", "tail", "grep", "find", "wc", "sort", "uniq",
    "echo", "pwd", "date", "whoami", "env", "python3", "pip", "pytest",
    "git", "jq", "npm", "node", "solana", "anchor",
}

BLOCKED_PATTERNS = [
    "|", ";", "&&", "||", "`", "$(",
    ">", ">>", "<", "<<",
    "rm -rf /", "rm -fr /", "chmod 777",
    "/etc/passwd", "/etc/shadow",
]

MAX_TIMEOUT = 60


@tool(
    name="shell_exec",
    description="Execute a whitelisted shell command. Only safe read-only and development commands are allowed.",
    permission="exec",
    requires_approval=True,
    input_schema={"type": "object", "properties": {"command": {"type": "string"}, "cwd": {"type": "string"}, "timeout": {"type": "integer"}}, "required": ["command"]},
)
async def shell_exec_async(args: dict[str, Any], context: dict[str, Any] | None = None) -> dict[str, Any]:
    command = args.get("command", "")
    cwd = args.get("cwd", context.get("project_root", ".") if context else ".")
    timeout = min(int(args.get("timeout", 30)), MAX_TIMEOUT)

    if not command:
        return {"success": False, "error": "Missing 'command' argument"}

    cmd_lower = command.lower().strip()
    for pattern in BLOCKED_PATTERNS:
        if pattern in cmd_lower:
            return {"success": False, "error": f"Blocked pattern detected: '{pattern}'. This command is not allowed."}

    try:
        cmd_parts = shlex.split(command)
    except ValueError as e:
        return {"success": False, "error": f"Invalid command syntax: {e}"}

    if not cmd_parts:
        return {"success": False, "error": "Empty command"}

    base_cmd = cmd_parts[0]
    if base_cmd not in ALLOWED_COMMANDS:
        return {"success": False, "error": f"Command '{base_cmd}' is not in the allowed command list. Allowed: {sorted(ALLOWED_COMMANDS)}"}

    if cwd:
        cwd_resolved = os.path.realpath(cwd)
        project_root = os.path.realpath(os.getcwd())
        if not cwd_resolved.startswith(project_root):
            return {"success": False, "error": f"Working directory must be within project root"}

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd_parts,
            cwd=cwd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        return {
            "success": proc.returncode == 0,
            "stdout": stdout.decode("utf-8", errors="replace")[:10000],
            "stderr": stderr.decode("utf-8", errors="replace")[:10000],
            "return_code": proc.returncode,
        }
    except asyncio.TimeoutError:
        return {"success": False, "error": f"Command timed out after {timeout}s"}
    except Exception as e:
        return {"success": False, "error": str(e)}


shell_exec = shell_exec_async
shell_exec._tool_definition = ToolDefinition(
    name="shell_exec",
    description="Execute a whitelisted shell command",
    handler=shell_exec_async,
    permission="exec",
    requires_approval=True,
    input_schema={"type": "object", "properties": {"command": {"type": "string"}, "cwd": {"type": "string"}, "timeout": {"type": "integer"}}, "required": ["command"]},
)
