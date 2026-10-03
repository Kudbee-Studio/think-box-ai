"""SSH-based remote execution provider (bounded first proof, no application-code bridge).

Executes a job's command on a remote host over SSH using the system `ssh` binary
(stdlib `subprocess` only — no new dependency). Host/user/key are configuration,
never hardcoded; the private key itself is never read, logged, or embedded — only
its filesystem path is passed to `ssh -i`.

This is deliberately the smallest possible provider satisfying the existing
`CloudExecutionProvider` interface (see provider.py). It does not talk to
apps/web, does not know about HERMES, and does not replace the hermetic provider
used by existing tests.
"""

from __future__ import annotations

import shlex
import subprocess
import time
from dataclasses import dataclass
from datetime import datetime, timezone

from thinkbox.cloud_execution.errors import CloudExecutionError
from thinkbox.cloud_execution.heartbeat import WorkerHeartbeat
from thinkbox.cloud_execution.job import ExecutionJob
from thinkbox.cloud_execution.provider import CloudExecutionProvider, ProviderRunResult
from thinkbox.cloud_execution.resources import ResourceLimits
from thinkbox.cloud_execution.workspace import WorkspaceBinding

PROVIDER_NAME = "ssh_remote"


@dataclass(frozen=True)
class SSHWorkerConfig:
    """Remote worker connection config. No secret material lives here — only a
    path to a private key file that must already exist on disk.

    When ``hardened`` is set, the host key must be verified against a trusted
    ``known_hosts`` file (``known_hosts_path``): the connection then uses
    ``StrictHostKeyChecking=yes`` + ``UserKnownHostsFile=<path>`` and never falls
    back to ``accept-new``. Hardened mode without a known_hosts source fails
    closed in :meth:`validate`.
    """

    host: str
    username: str = "root"
    private_key_path: str = ""
    port: int = 22
    connect_timeout_s: float = 10.0
    hardened: bool = False
    known_hosts_path: str = ""

    def validate(self) -> None:
        if not self.host:
            raise CloudExecutionError(
                error_type="InvalidSSHConfig", context={"reason": "host is required"}
            )
        if not self.username:
            raise CloudExecutionError(
                error_type="InvalidSSHConfig", context={"reason": "username is required"}
            )
        if self.hardened and not self.known_hosts_path:
            raise CloudExecutionError(
                error_type="InvalidSSHConfig",
                context={
                    "reason": "hardened mode requires a known_hosts_path to pin the host key",
                    "hint": "set UPCLOUD_SSH_KNOWN_HOSTS to a trusted known_hosts file",
                },
            )


class SSHCloudExecutionProvider(CloudExecutionProvider):
    """Runs a job's command on a remote host over SSH.

    The command to execute is read from ``job.metadata["command"]`` (a plain
    string, e.g. ``"hostname"``). This provider does not interpret or expand
    the command beyond shell quoting for the SSH argv — callers are
    responsible for keeping it bounded and safe.
    """

    def __init__(self, config: SSHWorkerConfig) -> None:
        config.validate()
        self._config = config
        self._available = True

    @property
    def name(self) -> str:
        return PROVIDER_NAME

    def is_available(self) -> bool:
        return self._available

    def set_available(self, available: bool) -> None:
        self._available = available

    def _ssh_argv(self, remote_command: str) -> list[str]:
        cfg = self._config
        argv = [
            "ssh",
            "-o", "BatchMode=yes",
            "-o", f"ConnectTimeout={int(cfg.connect_timeout_s)}",
            "-p", str(cfg.port),
        ]
        if cfg.hardened:
            # Pin the host key: never trust-on-first-use on a hardened connection.
            argv += ["-o", "StrictHostKeyChecking=yes"]
            argv += ["-o", f"UserKnownHostsFile={cfg.known_hosts_path}"]
        else:
            argv += ["-o", "StrictHostKeyChecking=accept-new"]
        if cfg.private_key_path:
            argv += ["-i", cfg.private_key_path]
        argv.append(f"{cfg.username}@{cfg.host}")
        argv.append(remote_command)
        return argv

    def run(
        self,
        job: ExecutionJob,
        limits: ResourceLimits,
        workspace: WorkspaceBinding,
    ) -> ProviderRunResult:
        if not self._available:
            raise CloudExecutionError(
                error_type="ProviderRunFailed",
                context={"reason": "provider marked unavailable"},
            )

        remote_command = str(job.metadata.get("command", "")).strip()
        if not remote_command:
            raise CloudExecutionError(
                error_type="ProviderRunFailed",
                context={"reason": "job.metadata['command'] is required and must be non-empty"},
            )

        argv = self._ssh_argv(remote_command)
        now = datetime.now(timezone.utc).isoformat()
        heartbeat = WorkerHeartbeat(
            worker_id=f"ssh_{self._config.host}",
            last_beat_at=now,
            interval_s=1.0,
            timeout_s=max(limits.wall_clock_timeout_s, 2.0),
        )

        start = time.monotonic()
        try:
            proc = subprocess.run(
                argv,
                capture_output=True,
                text=True,
                timeout=limits.wall_clock_timeout_s,
            )
        except subprocess.TimeoutExpired as exc:
            elapsed = time.monotonic() - start
            heartbeat.last_beat_at = "1970-01-01T00:00:00+00:00"
            return ProviderRunResult(
                success=False,
                exit_code=124,
                summary=f"ssh timeout after {elapsed:.2f}s: {remote_command!r}",
                heartbeat=heartbeat,
                metadata={
                    "host": self._config.host,
                    "command": remote_command,
                    "elapsed_s": elapsed,
                    "stdout": (exc.stdout or ""),
                    "stderr": (exc.stderr or ""),
                },
            )
        except FileNotFoundError as exc:
            raise CloudExecutionError(
                error_type="ProviderRunFailed",
                context={"reason": f"ssh binary not found: {exc}"},
            ) from exc

        elapsed = time.monotonic() - start
        stdout = proc.stdout.strip()
        stderr = proc.stderr.strip()
        success = proc.returncode == 0

        return ProviderRunResult(
            success=success,
            exit_code=proc.returncode,
            summary=stdout if success else (stderr or f"ssh exited {proc.returncode}"),
            artifact_refs=[f"ssh-stdout://{job.job_id}"] if success else [],
            heartbeat=heartbeat,
            metadata={
                "host": self._config.host,
                "username": self._config.username,
                "command": remote_command,
                "elapsed_s": elapsed,
                "stdout": stdout,
                "stderr": stderr,
                "argv_redacted": shlex.join(
                    [a if a != self._config.private_key_path else "<key-path-redacted>" for a in argv]
                ),
            },
        )
