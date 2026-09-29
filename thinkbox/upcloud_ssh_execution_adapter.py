"""Governed shell execution on the UpCloud worker over SSH (substrate ``upcloud-ssh``).

Same ``ExecutionReceipt`` + artifact + checkpoint contract as
``LocalExecutionAdapter``. The command runs on the remote worker through the
existing ``SSHCloudExecutionProvider``; stdout/stderr come back and are written to
a hash-verified local artifact.

Configuration uses the env vars already read by ``thinkbox.upcloud.UpCloudConfig``:
``UPCLOUD_SERVER_IP`` (required), ``UPCLOUD_SSH_USER`` (default ``root``) and
``UPCLOUD_SSH_KEY_PATH`` (required; a path to a private key file, which is never
read by Python). There is no fallback to local execution.
"""

from __future__ import annotations

import json
import os
import shlex
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from thinkbox.cloud_execution.errors import CloudExecutionError
from thinkbox.cloud_execution.job import ExecutionJob
from thinkbox.cloud_execution.provider import CloudExecutionProvider
from thinkbox.cloud_execution.providers.ssh_remote import (
    SSHCloudExecutionProvider,
    SSHWorkerConfig,
)
from thinkbox.cloud_execution.resources import ResourceLimits
from thinkbox.cloud_execution.workspace import WorkspaceBinding
from thinkbox.execution_adapter import (
    ExecutionReceipt,
    _id,
    _now,
    _sha256_bytes,
    _sha256_file,
)
from thinkbox.local_execution_adapter import (
    DEFAULT_TIMEOUT_SECONDS,
    _truncate,
    intent_fingerprint,
)
from thinkbox.repository import Repository

UPCLOUD_SSH_PROVIDER = "upcloud-ssh"
SSH_TRANSPORT_ERROR_EXIT = 255  # ssh(1) exits 255 on its own connection/auth errors
TIMEOUT_EXIT = 124  # SSHCloudExecutionProvider's timeout exit code


@dataclass(frozen=True)
class UpCloudSSHExecutionConfig:
    host: str = ""
    username: str = "root"
    private_key_path: str = ""
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS

    @classmethod
    def from_env(cls, environ: Mapping[str, str] | None = None) -> UpCloudSSHExecutionConfig:
        env = os.environ if environ is None else environ
        key = env.get("UPCLOUD_SSH_KEY_PATH", "").strip()
        return cls(
            host=env.get("UPCLOUD_SERVER_IP", "").strip(),
            username=env.get("UPCLOUD_SSH_USER", "").strip() or "root",
            private_key_path=os.path.expanduser(key) if key else "",
        )

    def is_complete(self) -> bool:
        return bool(self.host and self.username and self.private_key_path and Path(self.private_key_path).is_file())


class UpCloudSSHExecutionAdapter:
    """Execute one bounded shell command on the UpCloud worker; one artifact; one receipt."""

    provider = UPCLOUD_SSH_PROVIDER

    def __init__(
        self,
        repo: Repository | None = None,
        config: UpCloudSSHExecutionConfig | None = None,
        provider_factory: Callable[[SSHWorkerConfig], CloudExecutionProvider] | None = None,
    ) -> None:
        self._repo = repo or Repository()
        self._config = config or UpCloudSSHExecutionConfig.from_env()
        self._provider_factory = provider_factory or SSHCloudExecutionProvider

    def is_configured(self) -> bool:
        return self._config.is_complete()

    def execute(
        self,
        job_id: str,
        command: str = "",
        artifact_name: str = "artifact.json",
    ) -> ExecutionReceipt:
        execution_id = _id("exec")
        start = _now()
        receipt = ExecutionReceipt(
            job_id=job_id,
            execution_id=execution_id,
            provider=UPCLOUD_SSH_PROVIDER,
            artifact_name=artifact_name,
            start_time=start,
            provenance=["discover_upcloud_ssh", "execute_ssh"],
        )

        if not command.strip():
            receipt.status = "INVALID_COMMAND"
            receipt.error = "empty command"
            receipt.end_time = _now()
            receipt.provenance.append("fail_closed_empty_command")
            return receipt

        if not self.is_configured():
            receipt.status = "NOT_CONFIGURED"
            receipt.error = "UPCLOUD_SERVER_IP and an existing UPCLOUD_SSH_KEY_PATH are required"
            receipt.end_time = _now()
            receipt.provenance.append("fail_closed_not_configured")
            return receipt

        if self._repo.job_status(job_id) is None:
            self._repo.create_job(job_id=job_id, intent=command[:120], name="upcloud-ssh-exec")

        cfg = self._config
        ssh = self._provider_factory(
            SSHWorkerConfig(host=cfg.host, username=cfg.username, private_key_path=cfg.private_key_path)
        )
        cwd = Path(self._repo.path)
        try:
            result = ssh.run(
                ExecutionJob(job_id=job_id, intent=command[:120], metadata={"command": command}),
                ResourceLimits(
                    cpu_cores=1, memory_mb=256, wall_clock_timeout_s=float(cfg.timeout_seconds), max_concurrency=1
                ),
                WorkspaceBinding(workspace_id=job_id, worktree_path=str(cwd)),
            )
        except CloudExecutionError as exc:
            receipt.status = "SSH_FAILED"
            receipt.error = exc.error_type
            receipt.end_time = _now()
            receipt.provenance.append(f"ssh_error:{exc.error_type}")
            return receipt

        meta = result.metadata
        stdout, stdout_trunc = _truncate(str(meta.get("stdout", "")))
        stderr, stderr_trunc = _truncate(str(meta.get("stderr", "")))
        timed_out = result.exit_code == TIMEOUT_EXIT and "timeout" in result.summary
        receipt.exit_code = result.exit_code
        receipt.end_time = _now()

        payload: dict[str, Any] = {
            "provider": UPCLOUD_SSH_PROVIDER,
            "execution_id": execution_id,
            "job_id": job_id,
            "exit_code": result.exit_code,
            "timed_out": timed_out,
            "intent_fingerprint": intent_fingerprint(command),
            "command_argv_preview": shlex.split(command)[:8],
            "remote_host": cfg.host,
            "remote_user": cfg.username,
            "elapsed_s": meta.get("elapsed_s"),
            "stdout": stdout,
            "stderr": stderr,
            "stdout_truncated": stdout_trunc,
            "stderr_truncated": stderr_trunc,
        }
        artifact_body = json.dumps(payload, sort_keys=True)
        artifact_hash = _sha256_bytes(artifact_body.encode("utf-8"))
        artifacts_dir = cwd / ".thinkbox" / "artifacts"
        artifacts_dir.mkdir(parents=True, exist_ok=True)
        artifact_path = artifacts_dir / f"{execution_id}-{artifact_name}"
        artifact_path.write_text(artifact_body, encoding="utf-8")
        receipt.artifact_path = str(artifact_path)
        receipt.artifact_hash = artifact_hash
        receipt.verified = _sha256_file(artifact_path) == artifact_hash

        if timed_out:
            receipt.status = "TIMEOUT"
            receipt.provenance.append("timeout")
            return receipt
        if result.exit_code == SSH_TRANSPORT_ERROR_EXIT:
            receipt.status = "SSH_FAILED"
            receipt.error = stderr[:200] or "ssh transport error"
            receipt.provenance.append("ssh_transport_error")
            return receipt
        if receipt.verified and result.exit_code == 0:
            receipt.status = "COMPLETED"
            checkpoint = self._repo.checkpoint(
                execution_id,
                metadata={
                    "receipt_id": execution_id,
                    "provider": UPCLOUD_SSH_PROVIDER,
                    "remote_host": cfg.host,
                    "execution_start": start,
                    "execution_end": receipt.end_time,
                    "artifact_path": str(artifact_path),
                    "artifact_hash": artifact_hash,
                    "exit_code": result.exit_code,
                    "intent_fingerprint": payload["intent_fingerprint"],
                    "stdout_truncated": stdout_trunc,
                    "stderr_truncated": stderr_trunc,
                },
                job_id=job_id,
            )
            receipt.checkpoint_id = checkpoint.checkpoint_id
            receipt.receipt_path = str(
                self._repo.path / ".thinkbox" / "checkpoints" / f"{checkpoint.checkpoint_id}.json",
            )
            receipt.provenance.append("checkpoint_created")
            receipt.provenance.append("hash_verified")
        else:
            receipt.status = "EXIT_FAILED" if receipt.verified else "ARTIFACT_MISMATCH"
            receipt.provenance.append("verification_failed")
        return receipt
