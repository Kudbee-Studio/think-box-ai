"""Foundation layer — configuration, logging, errors, and bootstrap.

Layer 0. No dependencies on other thinkbox packages.
"""

from __future__ import annotations

from core.foundation.config import ThinkBoxConfig, load_config
from core.foundation.errors import (
    ApprovalDeniedError,
    GovernanceError,
    MemoryConflictError,
    MemoryError,
    MemoryKeyError,
    ProviderError,
    ProviderRateLimitError,
    ProviderUnavailableError,
    RuntimeError,
    ThinkBoxError,
    ThinkBoxLimitError,
    ToolApprovalRequiredError,
    ToolError,
    ToolNotFoundError,
    ToolPermissionError,
)
from core.foundation.logging import get_logger, setup_logging

# Bootstrap is imported lazily: it depends on governance/providers/tools modules
# that may not be implemented yet. Degrade gracefully if unavailable.
try:
    from core.foundation.bootstrap import RuntimeContext, bootstrap, shutdown
except ImportError:
    RuntimeContext = None  # type: ignore[assignment]
    bootstrap = None  # type: ignore[assignment]
    shutdown = None  # type: ignore[assignment]

__all__ = [
    "ThinkBoxConfig",
    "load_config",
    "setup_logging",
    "get_logger",
    "ThinkBoxError",
    "ProviderError",
    "ProviderUnavailableError",
    "ProviderRateLimitError",
    "MemoryError",
    "MemoryKeyError",
    "MemoryConflictError",
    "ToolError",
    "ToolNotFoundError",
    "ToolPermissionError",
    "ToolApprovalRequiredError",
    "GovernanceError",
    "ApprovalDeniedError",
    "RuntimeError",
    "ThinkBoxLimitError",
]
