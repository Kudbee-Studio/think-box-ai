"""Think execution adapter for Upstash Box remote execution.

The adapter connects Think Jobs to a controlled Upstash Box
execution surface. It is intentionally narrow: one job runs one
deterministic command and produces one verifiable artifact.

If no usable Upstash Box is configured, the adapter fails closed
and reports a deterministic NOT_CONFIGURED result. It never
pretends remote execution occurred.
"""

from __future__ import annotations

import hashlib
import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from thinkbox.repository import Repository

ENV_URL = "UPSTASH_PUBLIC_BOX_URL"
ENV_TOKEN = "UPSTASH_PUBLIC_BOX_TOKEN"
PROVIDER_NAME = "upstash_box"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _id(prefix: str) -> str:
    import uuid
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


@dataclass
class UpstashBoxConfig:
    url: str = ""
    token: str = ""
    box_id: str = ""
    env_url: str = ENV_URL
    env_token: str = ENV_TOKEN

    @classmethod
    def load_from_env(cls, **overrides: str) -> UpstashBoxConfig:
        url = overrides.get("url") or os.environ.get(cls.env_url, "")
        token = overrides.get("token") or os.environ.get(cls.env_token, "")
        box_id = ""
        if url:
            host = urlparse(url).hostname or ""
            box_id = host.split(".")[0] if host else ""
        return cls(
            url=url,
            token=token,
            box_id=box_id,
            env_url=cls.env_url,
            env_token=cls.env_token,
        )

    @property
    def is_configured(self) -> bool:
        return bool(self.url and self.token)


@dataclass
class ExecutionReceipt:
    job_id: str = ""
    execution_id: str = ""
    provider: str = PROVIDER_NAME
    box_id: str = ""
    box_url: str = ""
    status: str = "NOT_CONFIGURED"
    start_time: str = ""
    end_time: str = ""
    exit_code: int = -1
    artifact_name: str = ""
    artifact_path: str = ""
    artifact_hash: str = ""
    checkpoint_id: str = ""
    receipt_path: str = ""
    verified: bool = False
    error: str = ""
    provenance: list[str] = field(default_factory=list)


class UpstashBoxExecutionAdapter:
    """Adapter: Think Job -> Upstash Box -> artifact -> receipt."""

    def __init__(
        self,
        repo: Repository | None = None,
        config: UpstashBoxConfig | None = None,
    ) -> None:
        self._repo = repo or Repository()
        self._config = config or UpstashBoxConfig.load_from_env()

    def discover_env(self) -> dict[str, bool]:
        return {
            self._config.env_url: bool(self._config.url),
            self._config.env_token: bool(self._config.token),
        }

    def is_configured(self) -> bool:
        return self._config.is_configured

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
            box_id=self._config.box_id,
            box_url=self._config.url,
            artifact_name=artifact_name,
            start_time=start,
            provenance=["discover_env", "execute_remote"],
        )

        if not self.is_configured():
            receipt.status = "NOT_CONFIGURED"
            receipt.error = (
                f"{self._config.env_url} or {self._config.env_token} absent"
            )
            receipt.end_time = _now()
            receipt.provenance.append("fail_closed_no_config")
            return receipt

        if self._repo.job_status(job_id) is None:
            self._repo.create_job(
                job_id=job_id,
                intent=command[:120] if command else "remote execution",
                name="remote-exec",
            )

        try:
            result = self._post(execution_id, job_id, command, artifact_name)
        except Exception as exc:
            receipt.status = "REMOTE_FAILED"
            receipt.error = str(exc)
            receipt.end_time = _now()
            receipt.provenance.append(f"remote_error:{type(exc).__name__}")
            return receipt

        receipt.end_time = _now()
        artifact_path = self._write_artifact(result, artifact_name, execution_id)
        local_hash = _sha256_file(artifact_path)
        remote_hash = result.get("artifact_hash", "")
        receipt.exit_code = result.get("exit_code", -1)
        receipt.artifact_name = artifact_name
        receipt.artifact_path = str(artifact_path)
        receipt.artifact_hash = remote_hash
        receipt.verified = local_hash == remote_hash

        if receipt.verified and receipt.exit_code == 0:
            receipt.status = "COMPLETED"
            checkpoint = self._repo.checkpoint(
                execution_id,
                metadata={
                    "receipt_id": execution_id,
                    "execution_start": start,
                    "execution_end": receipt.end_time,
                    "artifact_path": str(artifact_path),
                    "artifact_hash": remote_hash,
                    "hostname": result.get("hostname", ""),
                    "os": result.get("os", ""),
                    "output": result.get("output", ""),
                },
                job_id=job_id,
            )
            receipt.checkpoint_id = checkpoint.checkpoint_id
            receipt.receipt_path = str(
                self._repo.path / ".thinkbox/checkpoints" / f"{checkpoint.checkpoint_id}.json"
            )
            receipt.provenance.append("checkpoint_created")
            receipt.provenance.append("hash_verified")
        else:
            receipt.status = "ARTIFACT_MISMATCH" if not receipt.verified else "EXIT_FAILED"
            receipt.provenance.append("verification_failed")

        return receipt

    def _post(
        self,
        execution_id: str,
        job_id: str,
        command: str,
        artifact_name: str,
    ) -> dict[str, Any]:
        payload = {
            "execution_id": execution_id,
            "job_id": job_id,
            "command": command,
            "artifact_name": artifact_name,
        }
        req = urllib.request.Request(
            f"{self._config.url.rstrip('/')}/run",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self._config.token}",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = resp.read().decode("utf-8")
            return json.loads(body) if body else {}

    def _write_artifact(
        self,
        result: dict[str, Any],
        artifact_name: str,
        execution_id: str,
    ) -> Path:
        artifacts_dir = self._repo.path / ".thinkbox" / "artifacts"
        artifacts_dir.mkdir(parents=True, exist_ok=True)
        artifact_path = artifacts_dir / f"{execution_id}-{artifact_name}"
        content = result.get("artifact_content", "")
        if isinstance(content, dict):
            content = json.dumps(content, sort_keys=True)
        artifact_path.write_text(str(content), encoding="utf-8")
        return artifact_path

    def verify(self, receipt: ExecutionReceipt) -> bool:
        if not receipt.artifact_path:
            return False
        path = Path(receipt.artifact_path)
        if not path.exists():
            return False
        return _sha256_file(path) == receipt.artifact_hash
