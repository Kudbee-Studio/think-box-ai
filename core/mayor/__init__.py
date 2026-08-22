"""Mayor control-plane package.

Exposes the canonical session boot mechanism. Use `mayor_boot` at the start
of every Mayor Cloud Agent session instead of re-discovering the repository.
"""

from core.mayor.boot import (
    DecisionRecord,
    MayorBootState,
    MemoryFile,
    boot_to_json,
    mayor_boot,
)

__all__ = [
    "mayor_boot",
    "MayorBootState",
    "DecisionRecord",
    "MemoryFile",
    "boot_to_json",
]
