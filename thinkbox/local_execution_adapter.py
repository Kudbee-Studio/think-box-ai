"""Local subprocess execution through the Think Box receipt contract.

Runs bounded commands in the repository worktree without cloud credentials.
Produces the same ``ExecutionReceipt`` + checkpoint shape as the remote
adapter, with ``provider='local'``. This is **not** LIVE VERIFIED remote
execution.
"""

from __future__ import annotations

import json
import platform
import shlex
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from thinkbox.execution_adapter import (
    ExecutionReceipt,
    _id,
    _now,
    _sha256_bytes,
    _sha256_file,
)
from thinkbox.kilo_hermetic_subprocess import run_bounded_command
from thinkbox.repository import Repository

LOCAL_PROVIDER = "local"
MAX_STDIO_CHARS = 4096
DEFAULT_TIMEOUT_SECONDS = 30


@dataclass(frozen=True)
class LocalExecutionConfig:
    """Bounded local execution settings."""

    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS


def _truncate(text: str, limit: int = MAX_STDIO_CHARS) -> tuple[str, bool]:
    if len(text) <= limit:
        return text, False
    return text[:limit], True


def intent_fingerprint(command: str) -> str:
    """Stable non-reversible identity for a command string."""
    normalized = command.strip()
    return _sha256_bytes(normalized.encode("utf-8"))[:16]


class LocalExecutionAdapter:
    """Execute one bounded shell command locally; one artifact; one receipt."""

    def __init__(
        self,
        repo: Repository | None = None,
        config: LocalExecutionConfig | None = None,
    ) -> None:
        self._repo = repo or Repository()
        self._config = config or LocalExecutionConfig()

    def is_configured(self) -> bool:
        return True

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
            provider=LOCAL_PROVIDER,
            artifact_name=artifact_name,
            start_time=start,
            provenance=["discover_local", "execute_subprocess"],
        )

        if not command.strip():
            receipt.status = "INVALID_COMMAND"
            receipt.error = "empty command"
            receipt.end_time = _now()
            receipt.provenance.append("fail_closed_empty_command")
            return receipt

        if self._repo.job_status(job_id) is None:
            self._repo.create_job(
                job_id=job_id,
                intent=command[:120],
                name="local-exec",
            )

        cwd = Path(self._repo.path)
        try:
            proc = run_bounded_command(
                ["/bin/sh", "-c", command],
                cwd=cwd,
                timeout_seconds=self._config.timeout_seconds,
            )
        except Exception as exc:
            receipt.status = "LOCAL_FAILED"
            receipt.error = str(exc)
            receipt.end_time = _now()
            receipt.provenance.append(f"local_error:{type(exc).__name__}")
            return receipt

        stdout, stdout_trunc = _truncate(proc.stdout)
        stderr, stderr_trunc = _truncate(proc.stderr)
        receipt.exit_code = proc.returncode
        receipt.end_time = _now()

        payload: dict[str, Any] = {
            "provider": LOCAL_PROVIDER,
            "execution_id": execution_id,
            "job_id": job_id,
            "exit_code": proc.returncode,
            "timed_out": proc.timed_out,
            "intent_fingerprint": intent_fingerprint(command),
            "command_argv_preview": shlex.split(command)[:8],
            "hostname": platform.node() or "local",
            "os": platform.system().lower(),
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

        if proc.timed_out:
            receipt.status = "TIMEOUT"
            receipt.provenance.append("timeout")
            return receipt

        if receipt.verified and proc.returncode == 0:
            receipt.status = "COMPLETED"
            checkpoint = self._repo.checkpoint(
                execution_id,
                metadata={
                    "receipt_id": execution_id,
                    "provider": LOCAL_PROVIDER,
                    "execution_start": start,
                    "execution_end": receipt.end_time,
                    "artifact_path": str(artifact_path),
                    "artifact_hash": artifact_hash,
                    "exit_code": proc.returncode,
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

    def verify(self, receipt: ExecutionReceipt) -> bool:
        if not receipt.artifact_path:
            return False
        path = Path(receipt.artifact_path)
        if not path.exists():
            return False
        return _sha256_file(path) == receipt.artifact_hash


def receipt_to_public_dict(receipt: ExecutionReceipt) -> dict[str, Any]:
    """Redacted receipt suitable for committed proof artifacts."""
    duration_ms: int | None = None
    if receipt.start_time and receipt.end_time:
        try:
            from datetime import datetime

            start = datetime.fromisoformat(receipt.start_time)
            end = datetime.fromisoformat(receipt.end_time)
            duration_ms = int((end - start).total_seconds() * 1000)
        except ValueError:
            duration_ms = None
    return {
        "job_id": receipt.job_id,
        "execution_id": receipt.execution_id,
        "provider": receipt.provider,
        "status": receipt.status,
        "verified": receipt.verified,
        "exit_code": receipt.exit_code,
        "start_time": receipt.start_time,
        "end_time": receipt.end_time,
        "duration_ms": duration_ms,
        "artifact_name": receipt.artifact_name,
        "artifact_hash": receipt.artifact_hash,
        "artifact_path_empty": receipt.artifact_path == "",
        "checkpoint_id": receipt.checkpoint_id or None,
        "receipt_path_empty": receipt.receipt_path == "",
        "error_empty": receipt.error == "",
        "provenance": list(receipt.provenance),
        "evidence_label": "verified",
        "live_verified": False,
        "live_api_called": False,
    }
