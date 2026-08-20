"""Browser plugin for kudbEE."""

from __future__ import annotations

import asyncio
from typing import Any

from backend.plugins.base import Tool, ToolResult


class BrowserTool(Tool):
    name = "browser"
    description = "Fetch web pages and return HTML content"
    permission = "network"
    requires_approval = True

    async def run(self, args: dict[str, Any], context: dict[str, Any]) -> ToolResult:
        url = args.get("url", "")
        if not url:
            return ToolResult(success=False, error="Missing 'url' argument")

        try:
            import aiohttp

            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                    text = await resp.text()
                    return ToolResult(
                        success=True,
                        data={
                            "url": url,
                            "status": resp.status,
                            "content": text[:50000],
                        },
                    )
        except asyncio.TimeoutError:
            return ToolResult(success=False, error=f"Request timed out after 30s")
        except Exception as e:
            return ToolResult(success=False, error=str(e))
