"""In-memory control-plane operation registry (hermetic; PR #154)."""

from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

__all__ = (
    "OperationState",
    "ControlPlaneOperation",
    "OperationRegistry",
    "get_operation_registry",
    "reset_operation_registry",
)


class OperationState(str, Enum):
    """Lifecycle states for a control-plane operation."""

    PENDING = "pending"
    ADMITTED = "admitted"
    RUNNING = "running"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    DENIED = "denied"


@dataclass
class ControlPlaneOperation:
    """One control-plane side-effect request (hermetic record)."""

    operation_id: str
    action_type: str
    state: OperationState = OperationState.PENDING
    receipt_id: str | None = None
    etag: str | None = None
    reason: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
    )
    updated_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "operation_id": self.operation_id,
            "action_type": self.action_type,
            "state": self.state.value,
            "receipt_id": self.receipt_id,
            "etag": self.etag,
            "reason": self.reason,
            "metadata": self.metadata,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "evidence_label": "simulated",
        }


class OperationRegistry:
    """Thread-safe hermetic store for control-plane operations."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._ops: dict[str, ControlPlaneOperation] = {}

    def create(
        self,
        operation_id: str,
        action_type: str,
        *,
        metadata: dict[str, Any] | None = None,
    ) -> ControlPlaneOperation | None:
        """Create operation; returns None if operation_id already exists."""
        with self._lock:
            if operation_id in self._ops:
                return None
            op = ControlPlaneOperation(
                operation_id=operation_id,
                action_type=action_type,
                metadata=dict(metadata or {}),
            )
            self._ops[operation_id] = op
            return op

    def get(self, operation_id: str) -> ControlPlaneOperation | None:
        with self._lock:
            return self._ops.get(operation_id)

    def list_operations(self, limit: int = 50) -> list[ControlPlaneOperation]:
        with self._lock:
            items = list(self._ops.values())
        items.sort(key=lambda o: o.created_at, reverse=True)
        return items[: max(1, min(limit, 200))]

    def transition(
        self,
        operation_id: str,
        state: OperationState,
        *,
        reason: str = "",
        receipt_id: str | None = None,
        etag: str | None = None,
    ) -> ControlPlaneOperation | None:
        with self._lock:
            op = self._ops.get(operation_id)
            if op is None:
                return None
            op.state = state
            op.reason = reason
            if receipt_id is not None:
                op.receipt_id = receipt_id
            if etag is not None:
                op.etag = etag
            op.updated_at = datetime.now(timezone.utc).isoformat()
            return op

    def cancel(self, operation_id: str, reason: str = "cancelled") -> ControlPlaneOperation | None:
        op = self.get(operation_id)
        if op is None:
            return None
        if op.state in (OperationState.COMPLETED, OperationState.CANCELLED, OperationState.DENIED):
            return op
        return self.transition(operation_id, OperationState.CANCELLED, reason=reason)

    def count(self) -> int:
        with self._lock:
            return len(self._ops)


_registry: OperationRegistry | None = None


def get_operation_registry() -> OperationRegistry:
    """Process-wide singleton (hermetic default)."""
    global _registry
    if _registry is None:
        _registry = OperationRegistry()
    return _registry


def reset_operation_registry() -> None:
    """Test helper: clear singleton."""
    global _registry
    _registry = OperationRegistry()


def new_receipt_id() -> str:
    """Generate a stable receipt id prefix for hermetic ops."""
    return f"rcpt_cp_{uuid.uuid4().hex[:16]}"
