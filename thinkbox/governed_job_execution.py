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
from thinkbox.repository import Repository

SUBSTRATE_LOCAL = "local"
SUBSTRATE_UPSTASH_BOX = "upstash-box"

_SUPPORTED = frozenset({SUBSTRATE_LOCAL, SUBSTRATE_UPSTASH_BOX})


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
) -> GovernedJobExecutionResult:
    """Run one bounded command through the governed execution adapter contract."""
    repository = repo or Repository()
    normalized = normalize_execution_substrate(substrate)
    adapter, provider = select_execution_adapter(normalized, repository)
    receipt = adapter.execute(job_id=job_id, command=command, artifact_name=artifact_name)
    proof = receipt_to_public_dict(receipt)
    proof["execution_substrate"] = normalized
    proof["adapter_selected"] = provider
    proof["governed_shell"] = True
    proof["live_verified"] = False
    proof["live_api_called"] = provider == UPSTASH_PROVIDER and receipt.status not in {
        "NOT_CONFIGURED",
        "INVALID_COMMAND",
    }
    return GovernedJobExecutionResult(
        substrate=normalized,
        adapter_provider=provider,
        receipt=receipt,
        public_proof=proof,
    )
