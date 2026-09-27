"""Base Tool class for kudbEE plugins."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ToolResult:
    """Result from a tool execution."""
    success: bool
    data: dict[str, Any] = field(default_factory=dict)
    error: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


class Tool(ABC):
    """Base class for all kudbEE tools/plugins."""

    name: str = "base"
    description: str = "Base tool"
    permission: str = "read_only"  # read_only | read_write | network | exec | restricted
    requires_approval: bool = False

    @abstractmethod
    async def run(self, args: dict[str, Any], context: dict[str, Any]) -> ToolResult:
        """Execute the tool with given arguments.

        Args:
            args: Tool-specific arguments
            context: Runtime context (project_root, session_id, etc.)

        Returns:
            ToolResult with success status and data/error
        """
        pass

    def to_schema(self) -> dict[str, Any]:
        """Return JSON schema for this tool's arguments."""
        return {
            "name": self.name,
            "description": self.description,
            "permission": self.permission,
            "requires_approval": self.requires_approval,
            "input_schema": {"type": "object", "properties": {}, "required": []},
        }
