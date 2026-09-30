"""Explicit substrate routing for governed Think Job shell execution.

``substrate=local`` selects ``LocalExecutionAdapter``. Remote substrates
require their own credentials; there is **no** silent fallback to local.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from thinkbox.execution_adapter import (
    PROVIDER_NAME as UPSTASH_PROVIDER,
    UpstashBoxExecutionAdapter,
)
from thinkbox.local_execution_adapter import LOCAL_PROVIDER, LocalExecutionAdapter, receipt_to_public_dict
from thinkbox.remote_exec_policy import ALLOWED_READONLY_COMMANDS
from thinkbox.repository import Repository
from thinkbox.upcloud_ssh_execution_adapter import UPCLOUD_SSH_PROVIDER, UpCloudSSHExecutionAdapter

SUBSTRATE_LOCAL = "local"
SUBSTRATE_UPSTASH_BOX = "upstash-box"
SUBSTRATE_UPCLOUD_SSH = "upcloud-ssh"

_SUPPORTED = frozenset({SUBSTRATE_LOCAL, SUBSTRATE_UPSTASH_BOX, SUBSTRATE_UPCLOUD_SSH})


class GovernedJobExecutionError(ValueError):
    """Invalid substrate or routing failure."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class _ExecutionAdapter(Protocol):
    provider: str

    def execute(self, job_id: str, command: str = "", artifact_name: str = "artifact.json") -> Any: ...


@dataclass(frozen=True)
class GovernedJobExecutionResult:
    """Outcome of one governed shell execution (redacted proof included)."""

    substrate: str
    adapter_provider: str
    receipt: Any
    public_proof: dict[str, Any]

    @property
    def verdict(self) -> str:
        return str(self.receipt.status)


def normalize_execution_substrate(substrate: str) -> str:
    """Return canonical substrate id or raise ``GovernedJobExecutionError``."""
    key = (substrate or "").strip().lower()
    if key not in _SUPPORTED:
        raise GovernedJobExecutionError(
            "unknown_substrate",
            f"unsupported execution substrate: {substrate!r} (supported: {sorted(_SUPPORTED)})",
        )
    return key


def select_execution_adapter(
    substrate: str,
    repo: Repository,
) -> tuple[_ExecutionAdapter, str]:
    """Pick adapter for an **explicit** substrate (never auto-detect)."""
    normalized = normalize_execution_substrate(substrate)
    if normalized == SUBSTRATE_LOCAL:
        return LocalExecutionAdapter(repo=repo), LOCAL_PROVIDER
    if normalized == SUBSTRATE_UPCLOUD_SSH:
        ssh_adapter = UpCloudSSHExecutionAdapter(repo=repo)
        if not ssh_adapter.is_configured():
            raise GovernedJobExecutionError(
                "remote_not_configured",
                "upcloud-ssh substrate requires UPCLOUD_SERVER_IP and an existing "
                "UPCLOUD_SSH_KEY_PATH; local fallback is prohibited",
            )
        return ssh_adapter, UPCLOUD_SSH_PROVIDER
    adapter = UpstashBoxExecutionAdapter(repo=repo)
    if not adapter.is_configured():
        raise GovernedJobExecutionError(
            "remote_not_configured",
            "upstash-box substrate requires configured UPSTASH_PUBLIC_BOX_URL and "
            "UPSTASH_PUBLIC_BOX_TOKEN; local fallback is prohibited",
        )
    return adapter, UPSTASH_PROVIDER


def execute_governed_job_command(
    *,
    substrate: str,
    job_id: str,
    command: str,
    repo: Repository | None = None,
    artifact_name: str = "governed_exec.json",
    install_packages: bool = False,
    package_manager: str = "upm",
) -> GovernedJobExecutionResult:
    """Run one bounded command through the governed execution adapter contract.

    Phase 1: Optional UPM dependency installation (LOCAL substrate only).
    - install_packages=True triggers frozen-lockfile dependency installation
    - package_manager must be "upm"; other values are rejected on non-LOCAL substrates
    - Remote substrates ignore install flags (no node.js guarantee)
    """
    normalized = normalize_execution_substrate(substrate)

    # Phase 1 validation: reject UPM installation on remote substrates
    if install_packages and normalized != SUBSTRATE_LOCAL:
        raise GovernedJobExecutionError(
            "unsupported_feature",
            f"package installation (install_packages=true) is only supported on {SUBSTRATE_LOCAL} substrate; "
            f"got substrate={normalized}",
        )

    if normalized == SUBSTRATE_UPCLOUD_SSH and command not in ALLOWED_READONLY_COMMANDS:
        # Enforced here, below every caller (run, resume, reclaim), so no path can reach the worker
        # with a command outside the read-only policy (thinkbox/remote_exec_policy.py).
        raise GovernedJobExecutionError(
            "command_not_allowed",
            "upcloud-ssh only runs the exact read-only commands in the remote execution policy",
        )
    repository = repo or Repository()
    adapter, provider = select_execution_adapter(normalized, repository)

    # Phase 1: Pass install flags only to LOCAL adapter; others ignore them
    if normalized == SUBSTRATE_LOCAL:
        receipt = adapter.execute(
            job_id=job_id,
            command=command,
            artifact_name=artifact_name,
            install_packages=install_packages,
            package_manager=package_manager,
        )
    else:
        receipt = adapter.execute(job_id=job_id, command=command, artifact_name=artifact_name)

    proof = receipt_to_public_dict(receipt)
    proof["execution_substrate"] = normalized
    proof["adapter_selected"] = provider
    proof["governed_shell"] = True
    proof["live_verified"] = False
    proof["live_api_called"] = provider in {UPSTASH_PROVIDER, UPCLOUD_SSH_PROVIDER} and receipt.status not in {
        "NOT_CONFIGURED",
        "INVALID_COMMAND",
    }
    return GovernedJobExecutionResult(
        substrate=normalized,
        adapter_provider=provider,
        receipt=receipt,
        public_proof=proof,
    )
