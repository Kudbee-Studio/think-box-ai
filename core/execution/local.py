"""Local subprocess execution provider for THINK BOX AI.

This is a REAL execution backend (not a mock). It runs commands on the host
via asyncio subprocesses and captures stdout/stderr/exit code. It is the
default fallback when a stronger isolation boundary (Firecracker) is not
available, and it is also used directly for trusted local work.

Governance (permission checks, audit logging, approval gates) remains the
responsibility of the layers ABOVE execution — this provider only performs
the mechanical act of running a command and returning its result.
"""

from __future__ import annotations

import asyncio
import shlex
import time
import uuid
from typing import Any

from core.execution.base import ExecResult, ExecutionProvider, ExecutionProviderRegistry
from core.foundation.logging import get_logger

logger = get_logger(__name__)


@ExecutionProviderRegistry.register("local")
class LocalExecProvider:
    """Execute commands as local subprocesses on the host."""

    name = "local"

    def __init__(self, config: "dict[str, Any] | None" = None) -> None:
        self._config = config or {}
        # Optional default working directory for all commands.
        self._cwd: str | None = self._config.get("cwd")
        # Allow callers to cap the maximum timeout (defense in depth).
        self._max_timeout: float = float(self._config.get("max_timeout", 3600.0))

    async def health_check(self) -> bool:
        """Local execution is always available on a running Python process."""
        return True

    async def execute(self, command: str, timeout: float = 30.0) -> ExecResult:
        """Run *command* via the system shell and capture its output.

        Args:
            command: Command string to execute.
            timeout: Seconds before the process is terminated.

        Returns:
            ExecResult describing the outcome.
        """
        if not command:
            return ExecResult(
                stdout="",
                stderr="",
                return_code=-1,
                duration=0.0,
                provider=self.name,
                error="Empty command",
            )

        effective_timeout = min(timeout, self._max_timeout)
        started = time.monotonic()
        try:
            cmd_parts = shlex.split(command)
            proc = await asyncio.create_subprocess_exec(
                *cmd_parts,
                cwd=self._cwd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            try:
                stdout, stderr = await asyncio.wait_for(
                    proc.communicate(), timeout=effective_timeout
                )
            except asyncio.TimeoutError:
                proc.kill()
                await proc.wait()
                duration = time.monotonic() - started
                return ExecResult(
                    stdout="",
                    stderr=f"Command timed out after {effective_timeout}s",
                    return_code=-1,
                    duration=duration,
                    provider=self.name,
                    error="timeout",
                )
            duration = time.monotonic() - started
            return ExecResult(
                stdout=stdout.decode("utf-8", errors="replace"),
                stderr=stderr.decode("utf-8", errors="replace"),
                return_code=proc.returncode or 0,
                duration=duration,
                provider=self.name,
            )
        except FileNotFoundError as e:
            duration = time.monotonic() - started
            return ExecResult(
                stdout="",
                stderr=str(e),
                return_code=-1,
                duration=duration,
                provider=self.name,
                error="command_not_found",
            )
        except Exception as e:  # noqa: BLE001 - surface as ExecResult, never swallow
            duration = time.monotonic() - started
            logger.error("Local execution failed", extra={"error": str(e)})
            return ExecResult(
                stdout="",
                stderr=str(e),
                return_code=-1,
                duration=duration,
                provider=self.name,
                error="execution_error",
            )

    async def shutdown(self) -> None:
        """No persistent resources to release for local execution."""
        return None
