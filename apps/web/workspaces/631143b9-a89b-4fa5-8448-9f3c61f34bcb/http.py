"""HTTP plugin for kudbEE."""

from __future__ import annotations

import asyncio
from typing import Any

import aiohttp

from backend.plugins.base import Tool, ToolResult


class HttpTool(Tool):
    name = "http"
    description = "Make HTTP requests (GET/POST)"
    permission = "network"
    requires_approval = True

    async def run(self, args: dict[str, Any], context: dict[str, Any]) -> ToolResult:
        url = args.get("url", "")
        method = args.get("method", "GET").upper()
        headers = args.get("headers", {})
        body = args.get("body")
        timeout = int(args.get("timeout", 30))

        if not url:
            return ToolResult(success=False, error="Missing 'url' argument")

        if method not in ("GET", "POST", "PUT", "DELETE", "PATCH"):
            return ToolResult(success=False, error=f"Unsupported method: {method}")

        try:
            async with aiohttp.ClientSession() as session:
                kwargs: dict[str, Any] = {"headers": headers, "timeout": aiohttp.ClientTimeout(total=timeout)}
                if body and method in ("POST", "PUT", "PATCH"):
                    kwargs["json"] = body

                async with session.request(method, url, **kwargs) as resp:
                    text = await resp.text()
                    return ToolResult(
                        success=True,
                        data={
                            "status": resp.status,
                            "headers": dict(resp.headers),
                            "body": text[:10000],  # Limit response size
                        },
                    )
        except asyncio.TimeoutError:
            return ToolResult(success=False, error=f"Request timed out after {timeout}s")
        except Exception as e:
            return ToolResult(success=False, error=str(e))
