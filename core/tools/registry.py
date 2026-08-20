"""Tool registry and decorator for THINK BOX AI."""

from __future__ import annotations

from typing import Any, Callable


class ToolDefinition:
    def __init__(
        self,
        name: str,
        description: str,
        handler: Callable | None = None,
        permission: str = "read_only",
        requires_approval: bool = False,
        schema: dict[str, Any] | None = None,
        input_schema: dict[str, Any] | None = None,
        output_schema: dict[str, Any] | None = None,
    ) -> None:
        self.name = name
        self.description = description
        self.handler = handler
        self.permission = permission
        self.requires_approval = requires_approval
        self.schema = schema or {}
        self.input_schema = input_schema or {}
        self.output_schema = output_schema or {}

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "permission": self.permission,
            "requires_approval": self.requires_approval,
            "input_schema": self.input_schema,
            "output_schema": self.output_schema,
        }


class ToolRegistry:
    def __init__(self, audit_log: Any = None) -> None:
        self._tools: dict[str, ToolDefinition] = {}
        self._audit_log = audit_log

    def register(self, tool: ToolDefinition) -> None:
        if tool.name in self._tools:
            from core.foundation.errors import ToolError
            raise ToolError(f"Tool already registered: {tool.name}")
        self._tools[tool.name] = tool
        if self._audit_log:
            self._audit_log.record(
                action="tool_register",
                actor="system",
                outcome="registered",
                metadata={"tool": tool.name},
            )

    def get(self, name: str) -> ToolDefinition | None:
        return self._tools.get(name)

    def list_tools(self) -> list[ToolDefinition]:
        return list(self._tools.values())

    def list_by_permission(self, permission: str) -> list[ToolDefinition]:
        return [t for t in self._tools.values() if t.permission == permission]

    def validate_input(self, tool_name: str, args: dict[str, Any]) -> bool:
        tool = self._tools.get(tool_name)
        if tool is None:
            from core.foundation.errors import ToolNotFoundError
            raise ToolNotFoundError(f"Tool not found: {tool_name}")
        required = tool.input_schema.get("required", list(tool.input_schema.keys()))
        missing = [k for k in required if k not in args]
        if missing:
            from core.foundation.errors import ToolError
            raise ToolError(f"Missing required fields: {missing}")
        return True


def tool(name: str, description: str = "", permission: str = "read_only", requires_approval: bool = False, input_schema: dict[str, Any] | None = None, output_schema: dict[str, Any] | None = None):
    def decorator(func: Callable) -> Callable:
        func._tool_definition = ToolDefinition(
            name=name,
            description=description or func.__doc__ or "",
            handler=func,
            permission=permission,
            requires_approval=requires_approval,
            input_schema=input_schema or {},
            output_schema=output_schema or {},
        )
        return func
    return decorator
