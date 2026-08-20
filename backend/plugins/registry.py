"""Plugin registry for kudbEE."""

from __future__ import annotations

from typing import Any

from backend.plugins.base import Tool
from backend.plugins.browser import BrowserTool
from backend.plugins.code_analyzer import CodeAnalyzerTool
from backend.plugins.docker import DockerTool
from backend.plugins.filesystem import FileListTool, FileReadTool, FileWriteTool
from backend.plugins.git import GitTool
from backend.plugins.http import HttpTool
from backend.plugins.terminal import TerminalTool
from backend.plugins.test_runner import TestRunnerTool


class PluginRegistry:
    """Registry of all available tools/plugins."""

    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}
        self._register_defaults()

    def _register_defaults(self) -> None:
        """Register default plugins."""
        defaults = [
            FileReadTool(),
            FileWriteTool(),
            FileListTool(),
            TerminalTool(),
            GitTool(),
            HttpTool(),
            BrowserTool(),
            TestRunnerTool(),
            CodeAnalyzerTool(),
            DockerTool(),
        ]
        for tool in defaults:
            self.register(tool)

    def register(self, tool: Tool) -> None:
        """Register a tool."""
        self._tools[tool.name] = tool

    def get(self, name: str) -> Tool | None:
        """Get a tool by name."""
        return self._tools.get(name)

    def list_tools(self) -> list[Tool]:
        """List all registered tools."""
        return list(self._tools.values())

    def get_enabled(self) -> list[Tool]:
        """Get all enabled tools (all by default)."""
        return list(self._tools.values())

    def list_tools(self) -> list[dict[str, Any]]:
        """List all registered tools with schemas."""
        return [tool.to_schema() for tool in self._tools.values()]

    def get_enabled(self) -> list[Tool]:
        """Get all enabled tools."""
        return list(self._tools.values())


# Global plugin registry
plugin_registry = PluginRegistry()
