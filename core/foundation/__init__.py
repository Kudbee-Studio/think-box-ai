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
from core.foundation.secrets import SecretResolver, SecretResolutionError

__all__ = [
    "ThinkBoxConfig",
    "load_config",
    "setup_logging",
    "get_logger",
    "SecretResolver",
    "SecretResolutionError",
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
