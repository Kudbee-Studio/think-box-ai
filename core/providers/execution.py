"""ExecutionProvider abstraction for THINK BOX AI.

Infrastructure providers (UpCloud, AWS, etc.) implement this interface.
The abstraction is provider-agnostic: core never imports provider-specific
code. Providers map verified capabilities onto infrastructure operations
and produce auditable evidence records.
"""

from __future__ import annotations

import abc
import datetime
import enum
from dataclasses import dataclass, field
from typing import Any, Optional

from core.foundation.errors import ThinkBoxError


class CapabilityStatus(str, enum.Enum):
    VERIFIED = "VERIFIED"
    DENIED = "DENIED"
    NOT_TESTED = "NOT_TESTED"
    REQUIRES_ADMIN_APPROVAL = "REQUIRES_ADMIN_APPROVAL"


@dataclass
class CapabilityCheck:
    capability: str
    status: CapabilityStatus
    detail: str = ""


@dataclass
class EvidenceRecord:
    job_id: str
    provider: str
    action: str
    auth_state: str
    result: str
    resource_id: str = ""
    timestamp: str = ""
    verification: str = ""
    dry_run: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.timestamp:
            self.timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()


@dataclass
class ExecutionPlan:
    job_id: str
    actions: list[dict[str, Any]] = field(default_factory=list)
    dry_run: bool = True
    estimated_cost: str = ""
    requires_approval: bool = False
    timestamp: str = ""

    def __post_init__(self) -> None:
        if not self.timestamp:
            self.timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()


@dataclass
class ExecutionResult:
    action: str
    success: bool
    resource_id: str = ""
    output: str = ""
    error: str = ""
    evidence: EvidenceRecord | None = None
    dry_run: bool = False


class ExecutionProviderCapabilities:
    list_servers: CapabilityStatus = CapabilityStatus.NOT_TESTED
    get_server: CapabilityStatus = CapabilityStatus.NOT_TESTED
    create_server: CapabilityStatus = CapabilityStatus.NOT_TESTED
    delete_server: CapabilityStatus = CapabilityStatus.NOT_TESTED
    list_storage: CapabilityStatus = CapabilityStatus.NOT_TESTED
    get_storage: CapabilityStatus = CapabilityStatus.NOT_TESTED
    create_storage: CapabilityStatus = CapabilityStatus.NOT_TESTED
    delete_storage: CapabilityStatus = CapabilityStatus.NOT_TESTED
    list_networks: CapabilityStatus = CapabilityStatus.NOT_TESTED
    get_ip: CapabilityStatus = CapabilityStatus.NOT_TESTED
    assign_ip: CapabilityStatus = CapabilityStatus.NOT_TESTED
    list_locations: CapabilityStatus = CapabilityStatus.NOT_TESTED
    discover_gpu: CapabilityStatus = CapabilityStatus.NOT_TESTED
    check_availability: CapabilityStatus = CapabilityStatus.NOT_TESTED
    create_server_from_template: CapabilityStatus = CapabilityStatus.NOT_TESTED
    reboot_server: CapabilityStatus = CapabilityStatus.NOT_TESTED


class ExecutionProvider(abc.ABC):
    """Abstract base for infrastructure execution providers."""

    def __init__(self, config: dict[str, Any]) -> None:
        self._config = config
        self._auth_checked: bool = False
        self._auth_status: str = "untested"
        self._capabilities: ExecutionProviderCapabilities | None = None
        self._evidence: list[EvidenceRecord] = []

    @property
    @abc.abstractmethod
    def provider_name(self) -> str: ...

    @property
    def auth_status(self) -> str:
        return self._auth_status

    @property
    def capabilities(self) -> ExecutionProviderCapabilities:
        if self._capabilities is None:
            self._capabilities = ExecutionProviderCapabilities()
        return self._capabilities

    @property
    def evidence(self) -> list[EvidenceRecord]:
        return list(self._evidence)

    def _record_evidence(
        self,
        job_id: str,
        action: str,
        auth_state: str,
        result: str,
        resource_id: str = "",
        verification: str = "",
        dry_run: bool = False,
        metadata: dict[str, Any] | None = None,
    ) -> EvidenceRecord:
        record = EvidenceRecord(
            job_id=job_id,
            provider=self.provider_name,
            action=action,
            auth_state=auth_state,
            result=result,
            resource_id=resource_id,
            verification=verification,
            dry_run=dry_run,
            metadata=metadata or {},
        )
        self._evidence.append(record)
        return record

    @abc.abstractmethod
    def check_auth(self) -> CapabilityCheck: ...

    @abc.abstractmethod
    def discover_capabilities(self) -> list[CapabilityCheck]: ...

    def plan(
        self,
        job_id: str,
        actions: list[dict[str, Any]],
        dry_run: bool = True,
    ) -> ExecutionPlan:
        plan = ExecutionPlan(
            job_id=job_id,
            actions=actions,
            dry_run=dry_run,
            requires_approval=any(
                a.get("destructive", False) or a.get("billable", False)
                for a in actions
            ),
        )
        self._record_evidence(
            job_id=job_id,
            action="plan",
            auth_state=self._auth_status,
            result=f"Plan generated with {len(actions)} actions (dry_run={dry_run})",
            verification="plan_only",
            dry_run=True,
        )
        return plan

    @abc.abstractmethod
    def execute(
        self,
        job_id: str,
        action: str,
        params: dict[str, Any] | None = None,
        approve: bool = False,
    ) -> ExecutionResult: ...


class ProviderExecutionRegistry:
    """Registry of infrastructure execution providers."""

    _providers: dict[str, type] = {}

    @classmethod
    def register(cls, name: str) -> callable:
        def decorator(provider_cls: type) -> type:
            cls._providers[name] = provider_cls
            return provider_cls
        return decorator

    @classmethod
    def get(cls, name: str) -> type | None:
        return cls._providers.get(name)

    @classmethod
    def list_providers(cls) -> list[str]:
        return list(cls._providers.keys())
