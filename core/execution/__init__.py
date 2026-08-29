"""Execution substrate for THINK BOX AI.

The Execution layer is a NEW architectural concern that sits *below* the
Runtime layer (Agent/ThinkBox/Planner/Actor) and *above* the host OS. It is
the isolated place where untrusted Think Box work actually happens.

It is deliberately separate from:
  - Governance/Tools  (permissions, audit, tool definitions)
  - Providers        (model intelligence)
  - Memory           (context/state)
  - Runtime          (orchestration of thought)

Firecracker is one ExecutionProvider implementation within this layer. The
runtime must never depend on Firecracker internals directly — only on the
`ExecutionProvider` protocol defined here.
"""

from __future__ import annotations

from core.execution.base import (
    ExecResult,
    ExecutionProvider,
    ExecutionProviderRegistry,
    ExecutionUnavailableError,
)
from core.execution.local import LocalExecProvider

__all__ = [
    "ExecResult",
    "ExecutionProvider",
    "ExecutionProviderRegistry",
    "ExecutionUnavailableError",
    "LocalExecProvider",
]
