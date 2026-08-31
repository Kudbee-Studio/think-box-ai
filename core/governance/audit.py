"""Governance layer for THINK BOX AI.

Provides audit logging, permission checking, and approval gates.
Integrates with the tool registry to enforce permission policies.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
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
class AuditEntry:
    action: str
    actor: str
    outcome: str
    metadata: dict[str, Any]
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass
class AuditLog:
    store: Any = None
    _entries: list[AuditEntry] = field(default_factory=list, repr=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def record(self, action: str, actor: str, outcome: str, metadata: dict[str, Any] | None = None) -> None:
        entry = AuditEntry(
            action=action,
            actor=actor,
            outcome=outcome,
            metadata=metadata or {},
        )
        with self._lock:
            self._entries.append(entry)
        logger.debug(f"audit: {action} by {actor} → {outcome}")

    def list_entries(self, limit: int = 100) -> list[AuditEntry]:
        with self._lock:
            return self._entries[-limit:]

    def count(self) -> int:
        with self._lock:
            return len(self._entries)


@dataclass
class PermissionChecker:
    policy: ApprovalPolicy = ApprovalPolicy.AUTO_APPROVE_READ

    def check(self, permission: str | PermissionLevel) -> bool:
        permission_value = permission.value if isinstance(permission, PermissionLevel) else permission
        if self.policy == ApprovalPolicy.AUTO_APPROVE_ALL:
            return True
        if self.policy == ApprovalPolicy.AUTO_APPROVE_READ and permission_value == PermissionLevel.READ_ONLY.value:
            return True
        return False

    def requires_approval(self, permission: str | PermissionLevel) -> bool:
        return not self.check(permission)


@dataclass
class ApprovalGate:
    permission_checker: PermissionChecker
    audit_log: AuditLog

    def require_approval(self, tool_name: str, permission: str, context: dict[str, Any]) -> bool:
        """Returns True if approval is required (operation should be blocked)."""
        allowed = self.permission_checker.check(permission)
        self.audit_log.record(
            action=f"approval_check:{tool_name}",
            actor=context.get("agent_id", "system"),
            outcome="allowed" if allowed else "pending",
            metadata={"permission": permission, "tool": tool_name},
        )
        return not allowed

    def execute_with_approval(self, tool_name: str, permission: str, context: dict[str, Any], fn, *args, **kwargs):
        """Execute a function if approval is granted, otherwise raise."""
        if self.require_approval(tool_name, permission, context):
            raise PermissionError(f"Approval required for {tool_name} (permission: {permission})")
        return fn(*args, **kwargs)
