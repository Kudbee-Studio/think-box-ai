"""Execution provider abstractions for THINK BOX AI.

Defines the contract that all execution backends (local subprocess,
Firecracker microVM, future Cloud Hypervisor, etc.) must satisfy, plus the
registry that the runtime uses to select an implementation by name.

This module is part of the Execution layer and depends only on the
Foundation layer (stdlib, logging, errors).
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

from core.foundation.errors import ThinkBoxError
from core.foundation.logging import get_logger

logger = get_logger(__name__)


class ExecutionUnavailableError(ThinkBoxError):
    """Raised when an ExecutionProvider cannot perform work on this host."""

    error_type: str = field(default="execution_unavailable")
    message: str = "Execution provider is unavailable on this host"


@dataclass
class ExecResult:
    """Result of running a command through an ExecutionProvider.

    Every execution backend returns this same structure so the runtime
    (and governance/audit above it) can treat local and microVM execution
    identically.
    """

    stdout: str
    stderr: str
    return_code: int
    duration: float
    provider: str = ""
    microvm_id: str | None = None
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@runtime_checkable
class ExecutionProvider(Protocol):
    """Protocol that every execution backend implements."""

    name: str

    async def execute(self, command: str, timeout: float = 30.0) -> ExecResult:
        """Execute *command* and return captured result.

        Args:
            command: Shell command to run inside the execution environment.
            timeout: Maximum wall-clock seconds before forced termination.

        Returns:
            ExecResult with stdout/stderr/return_code and provider metadata.
        """
        ...

    async def health_check(self) -> bool:
        """Return True if this provider can execute on the current host."""
        ...

    async def shutdown(self) -> None:
        """Release any held resources (processes, sockets, microVMs)."""
        ...


class ExecutionProviderRegistry:
    """Registry mapping provider names to their implementations.

    Mirrors the shape of ``core.providers.base.ProviderRegistry`` so the
    two registries share a consistent discovery pattern.
    """

    _providers: dict[str, type] = {}

    @classmethod
    def register(cls, name: str) -> "callable":
        def decorator(provider_cls: type) -> type:
            cls._providers[name] = provider_cls
            logger.debug("Registered execution provider", extra={"name": name})
            return provider_cls

        return decorator

    @classmethod
    def get(cls, name: str) -> "type | None":
        return cls._providers.get(name)

    @classmethod
    def list_providers(cls) -> "list[str]":
        return list(cls._providers.keys())

    @classmethod
    def create(cls, name: str, config: "dict[str, Any] | None" = None) -> "ExecutionProvider":
        """Instantiate a registered provider by name.

        Raises:
            ExecutionUnavailableError: if the name is unknown.
        """
        provider_cls = cls.get(name)
        if provider_cls is None:
            raise ExecutionUnavailableError(message=f"Unknown execution provider: {name}")
        return provider_cls(config or {})
