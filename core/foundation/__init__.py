"""Foundation layer — configuration, logging, errors, and bootstrap.

Layer 0. No dependencies on other thinkbox packages.
"""

from __future__ import annotations

from core.foundation.bootstrap import RuntimeContext, bootstrap, shutdown
from core.foundation.config import ThinkBoxConfig, load_config
from core.foundation.errors import (
    ApprovalDeniedError,
    MemoryConflictError,
    MemoryError,
    MemoryKeyError,
    ProviderError,
    ProviderRateLimitError,
    ProviderUnavailableError,
    ThinkBoxError,
    ThinkBoxLimitError,
    ToolApprovalRequiredError,
    ToolError,
    ToolNotFoundError,
    ToolPermissionError,
)
from core.foundation.logging import get_logger, setup_logging

__all__ = [
    "ThinkBoxConfig",
    "load_config",
    "RuntimeContext",
    "bootstrap",
    "shutdown",
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
