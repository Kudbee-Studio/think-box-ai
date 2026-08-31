"""Shell execution tool for THINK BOX AI.

When HARNESS=1 (or config sandbox.enabled=true) and Docker is reachable,
commands run inside an isolated Docker container via HarnessRunner.
Set HARNESS=0 to fall back to host subprocess (dev fallback).
"""

from __future__ import annotations

import asyncio
import logging
import os
import shlex
from typing import Any

from core.tools.registry import ToolDefinition, tool

logger = logging.getLogger("thinkbox.tools.shell_exec")


class HarnessSession:
    """Per-agent Docker container session for shell execution.

    Lazily starts a container on first exec(). Each agent_id gets its
    own container; the session registry is process-global so repeated
    calls from the same agent reuse the container.
    """

    _sessions: dict[str, HarnessSession] = {}

    def __init__(self, agent_id: str) -> None:
        self.agent_id = agent_id
        self._container_id: str | None = None
        self._runner = None

    @classmethod
    def get(cls, agent_id: str) -> HarnessSession:
        if agent_id not in cls._sessions:
            cls._sessions[agent_id] = cls(agent_id)
        return cls._sessions[agent_id]

    @classmethod
    def drop(cls, agent_id: str) -> None:
        session = cls._sessions.pop(agent_id, None)
        if session is not None:
            session.cleanup()

    async def _ensure_container(self) -> str:
        if self._container_id is not None:
            return self._container_id

        from core.runtime.harness import HarnessConfig, HarnessRunner

        network_mode = os.environ.get("HARNESS_NETWORK", "none")
        config = HarnessConfig(
            enabled=True,
            network_mode=network_mode,
        )
        runner = HarnessRunner(config)

        container = runner.start_container(
            agent_id=self.agent_id,
            limits=config.limits,
            mounts={},
            network_mode=network_mode,
        )

        self._runner = runner
        self._container_id = container.container_id
        return self._container_id

    async def exec(
        self,
        command: str,
        timeout: int = 60,
        env: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        container_id = await self._ensure_container()
        assert self._runner is not None
        return await self._runner.exec_in_container(
            container_id,
            ["sh", "-c", command],
            timeout=timeout,
            env=env,
        )

    def cleanup(self) -> None:
        if self._runner is not None and self._container_id is not None:
            self._runner.stop_container(self._container_id)
            self._container_id = None
            self._runner = None


def _harness_enabled() -> bool:
    flag = os.environ.get("HARNESS", "")
    if flag == "1":
        return True
    if flag == "0":
        return False
    from core.runtime.harness import docker_available

    if not docker_available():
        logger.warning("HARNESS defaulted off: docker not reachable")
        return False
    return True


@tool(
    name="shell_exec",
    description="Execute a shell command",
    permission="exec",
    requires_approval=True,
    input_schema={"type": "object", "properties": {"command": {"type": "string"}, "cwd": {"type": "string"}, "timeout": {"type": "integer"}}, "required": ["command"]},
)
async def shell_exec_async(args: dict[str, Any], context: dict[str, Any] | None = None) -> dict[str, Any]:
    command = args.get("command", "")
    timeout = int(args.get("timeout", 30))
    if not command:
        return {"success": False, "error": "Missing 'command' argument"}

    if _harness_enabled():
        agent_id = (context or {}).get("agent_id", f"shell-{os.getpid()}")
        session = HarnessSession.get(agent_id)
        return await session.exec(command, timeout=timeout)

    cwd = args.get("cwd", context.get("project_root", ".") if context else ".")
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
