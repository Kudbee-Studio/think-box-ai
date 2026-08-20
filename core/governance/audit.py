"""Governance layer for THINK BOX AI."""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from core.foundation.logging import get_logger

logger = get_logger(__name__)


class ApprovalPolicy(str, Enum):
    MANUAL = "manual"
    AUTO_APPROVE_READ = "auto_approve_read"
    AUTO_APPROVE_ALL = "auto_approve_all"


class PermissionLevel(str, Enum):
    READ_ONLY = "read_only"
    READ_WRITE = "read_write"
    NETWORK = "network"
    EXEC = "exec"
    RESTRICTED = "restricted"


@dataclass
class AuditLog:
    store: Any = None
    _entries: list[dict[str, Any]] = field(default_factory=list, repr=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def record(self, action: str, actor: str, outcome: str, metadata: dict[str, Any] | None = None) -> None:
        with self._lock:
            entry = {
                "action": action,
                "actor": actor,
                "outcome": outcome,
                "metadata": metadata or {},
                "timestamp": __import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat(),
            }
            self._entries.append(entry)
            logger.debug("Audit recorded", extra={"action": action, "actor": actor, "outcome": outcome})

    def list_entries(self) -> list[dict[str, Any]]:
        with self._lock:
            return list(self._entries)


@dataclass
class PermissionChecker:
    policy: ApprovalPolicy = ApprovalPolicy.MANUAL

    def check(self, permission: str | PermissionLevel) -> bool:
        permission_value = permission.value if isinstance(permission, PermissionLevel) else permission
        if self.policy == ApprovalPolicy.AUTO_APPROVE_ALL:
            return True
        if self.policy == ApprovalPolicy.AUTO_APPROVE_READ and permission_value == PermissionLevel.READ_ONLY.value:
            return True
        return False


@dataclass
class ApprovalGate:
    permission_checker: PermissionChecker
    audit_log: AuditLog

    def require_approval(self, tool_name: str, permission: str, context: dict[str, Any]) -> bool:
        allowed = self.permission_checker.check(permission)
        self.audit_log.record(
            action=f"approval_check:{tool_name}",
            actor=context.get("agent_id", "unknown"),
            outcome="allowed" if allowed else "pending",
            metadata={"permission": permission, "tool": tool_name},
        )
        return not allowed
