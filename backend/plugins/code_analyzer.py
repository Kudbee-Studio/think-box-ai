"""Code analyzer plugin for kudbEE."""

from __future__ import annotations

import ast
import os
from typing import Any

from backend.plugins.base import Tool, ToolResult


class CodeAnalyzerTool(Tool):
    name = "code_analyzer"
    description = "Analyze code structure and complexity"
    permission = "read_only"
    requires_approval = False

    async def run(self, args: dict[str, Any], context: dict[str, Any]) -> ToolResult:
        file_path = args.get("path", "")
        if not file_path:
            return ToolResult(success=False, error="Missing 'path' argument")

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                source = f.read()

            tree = ast.parse(source)
            functions = []
            classes = []

            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    functions.append({
                        "name": node.name,
                        "line": node.lineno,
                        "args": [arg.arg for arg in node.args.args],
                    })
                elif isinstance(node, ast.ClassDef):
                    classes.append({
                        "name": node.name,
                        "line": node.lineno,
                    })

            return ToolResult(
                success=True,
                data={
                    "file": file_path,
                    "lines": len(source.splitlines()),
                    "functions": functions,
                    "classes": classes,
                },
            )
        except FileNotFoundError:
            return ToolResult(success=False, error=f"File not found: {file_path}")
        except SyntaxError as e:
            return ToolResult(success=False, error=f"Syntax error: {e}")
        except Exception as e:
            return ToolResult(success=False, error=str(e))
