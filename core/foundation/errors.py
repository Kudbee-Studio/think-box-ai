"""Structured error types for THINK BOX AI.

All errors carry:
  - agent_id, task_id, think_box_id
  - timestamp, error_type, context

The runtime raises structured errors. It does not log and continue.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class ThinkBoxError(Exception):
    """Base class for all THINK BOX AI errors."""

    agent_id: str = ""
    task_id: str = ""
    think_box_id: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    error_type: str = "think_box_error"
    context: dict = field(default_factory=dict)
    message: str = "An unexpected error occurred"

    def __str__(self) -> str:
        parts = [f"[{self.error_type}] {self.message}"]
        if self.agent_id:
            parts.append(f"agent={self.agent_id}")
        if self.task_id:
            parts.append(f"task={self.task_id}")
        if self.think_box_id:
            parts.append(f"think_box={self.think_box_id}")
        if self.context:
            parts.append(f"context={self.context}")
        return " | ".join(parts)


@dataclass
class ProviderError(ThinkBoxError):
    error_type: str = field(default="provider_error")


@dataclass
class ProviderUnavailableError(ProviderError):
    error_type: str = field(default="provider_unavailable")
    message: str = "Model provider is unavailable"


@dataclass
class ProviderRateLimitError(ProviderError):
    error_type: str = field(default="provider_rate_limit")
    message: str = "Model provider rate limit exceeded"


@dataclass
class ProviderAuthError(ProviderError):
    error_type: str = field(default="provider_auth")
    message: str = "Model provider authentication failed"


@dataclass
class ProviderPaymentRequiredError(ProviderError):
    error_type: str = field(default="provider_payment_required")
    message: str = "Model provider requires payment or credits"


@dataclass
class MemoryError(ThinkBoxError):
    error_type: str = field(default="memory_error")


@dataclass
class MemoryKeyError(MemoryError):
    error_type: str = field(default="memory_key_error")
    message: str = "Memory key not found or invalid"


@dataclass
class MemoryConflictError(MemoryError):
    error_type: str = field(default="memory_conflict")
    message: str = "Concurrent memory write conflict"


@dataclass
class ToolError(ThinkBoxError):
    error_type: str = field(default="tool_error")


@dataclass
class ToolNotFoundError(ToolError):
    error_type: str = field(default="tool_not_found")
    message: str = "Tool not found in registry"


@dataclass
class ToolPermissionError(ToolError):
    error_type: str = field(default="tool_permission_denied")
    message: str = "Permission denied for tool"


@dataclass
class ToolApprovalRequiredError(ToolError):
    error_type: str = field(default="tool_approval_required")
    message: str = "Tool requires approval before execution"


@dataclass
class GovernanceError(ThinkBoxError):
    error_type: str = field(default="governance_error")


@dataclass
class ApprovalDeniedError(GovernanceError):
    error_type: str = field(default="approval_denied")
    message: str = "Required approval was denied"


@dataclass
class RuntimeError(ThinkBoxError):
    error_type: str = field(default="runtime_error")


@dataclass
class ThinkBoxLimitError(RuntimeError):
    error_type: str = field(default="think_box_limit_exceeded")
    message: str = "Maximum Think Box nesting depth exceeded"
