"""Unit tests for core.tools — using unittest."""

from __future__ import annotations

import asyncio
import unittest
from unittest.mock import MagicMock

from core.foundation.errors import ToolError, ToolNotFoundError
from core.governance.audit import AuditLog, PermissionLevel
from core.tools.registry import ToolDefinition, ToolRegistry, tool


class TestToolRegistry(unittest.TestCase):
    def test_register_and_get(self) -> None:
        mock_store = MagicMock()
        audit = AuditLog(mock_store)
        registry = ToolRegistry(audit)
        tool_def = ToolDefinition(
            name="test_tool",
            description="A test tool",
            input_schema={"arg": "str"},
            output_schema={"result": "str"},
            permission=PermissionLevel.READ_ONLY,
        )
        registry.register(tool_def)
        retrieved = registry.get("test_tool")
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.name, "test_tool")

    def test_register_duplicate_raises(self) -> None:
        mock_store = MagicMock()
        audit = AuditLog(mock_store)
        registry = ToolRegistry(audit)
        tool_def = ToolDefinition(
            name="dup_tool",
            description="",
            input_schema={},
            output_schema={},
        )
        registry.register(tool_def)
        with self.assertRaises(ToolError):
            registry.register(tool_def)

    def test_get_missing_returns_none(self) -> None:
        mock_store = MagicMock()
        audit = AuditLog(mock_store)
        registry = ToolRegistry(audit)
        self.assertIsNone(registry.get("nonexistent"))

    def test_validate_input_success(self) -> None:
        mock_store = MagicMock()
        audit = AuditLog(mock_store)
        registry = ToolRegistry(audit)
        tool_def = ToolDefinition(
            name="test",
            description="",
            input_schema={"arg1": "str", "arg2": "int"},
            output_schema={},
        )
        registry.register(tool_def)
        self.assertTrue(registry.validate_input("test", {"arg1": "hello", "arg2": 42}))

    def test_validate_input_missing_fields(self) -> None:
        mock_store = MagicMock()
        audit = AuditLog(mock_store)
        registry = ToolRegistry(audit)
        tool_def = ToolDefinition(
            name="test",
            description="",
            input_schema={"arg1": "str"},
            output_schema={},
        )
        registry.register(tool_def)
        with self.assertRaises(ToolError):
            registry.validate_input("test", {})

    def test_validate_input_missing_tool(self) -> None:
        mock_store = MagicMock()
        audit = AuditLog(mock_store)
        registry = ToolRegistry(audit)
        with self.assertRaises(ToolNotFoundError):
            registry.validate_input("nonexistent", {})

    def test_list_tools(self) -> None:
        mock_store = MagicMock()
        audit = AuditLog(mock_store)
        registry = ToolRegistry(audit)
        registry.register(ToolDefinition(name="t1", description="", input_schema={}, output_schema={}))
        registry.register(ToolDefinition(name="t2", description="", input_schema={}, output_schema={}))
        self.assertEqual(len(registry.list_tools()), 2)

    def test_list_by_permission(self) -> None:
        mock_store = MagicMock()
        audit = AuditLog(mock_store)
        registry = ToolRegistry(audit)
        registry.register(ToolDefinition(name="t1", description="", input_schema={}, output_schema={}, permission=PermissionLevel.READ_ONLY))
        registry.register(ToolDefinition(name="t2", description="", input_schema={}, output_schema={}, permission=PermissionLevel.EXEC))
        readonly = registry.list_by_permission(PermissionLevel.READ_ONLY)
        self.assertEqual(len(readonly), 1)
        self.assertEqual(readonly[0].name, "t1")


class TestToolDecorator(unittest.TestCase):
    def test_decorator_registers_tool(self) -> None:
        mock_store = MagicMock()
        audit = AuditLog(mock_store)

        @tool(
            name="decorated_tool",
            description="A decorated tool",
            input_schema={"x": "int"},
            permission=PermissionLevel.READ_ONLY,
        )
        async def my_tool(input: dict) -> dict:
            return {"result": input["x"] * 2}

        tool_def = my_tool._tool_definition
        self.assertEqual(tool_def.name, "decorated_tool")
        self.assertEqual(tool_def.handler, my_tool)

    def test_decorator_async(self) -> None:
        mock_store = MagicMock()
        audit = AuditLog(mock_store)

        @tool(
            name="async_tool",
            description="",
            input_schema={},
            permission=PermissionLevel.READ_ONLY,
        )
        async def async_func(input: dict) -> dict:
            return {"ok": True}

        result = asyncio.run(async_func({}))
        self.assertEqual(result, {"ok": True})


if __name__ == "__main__":
    unittest.main()
