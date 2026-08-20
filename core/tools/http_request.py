"""HTTP request tool for THINK BOX AI."""

from __future__ import annotations

import asyncio
import json
from typing import Any

from core.tools.registry import ToolDefinition, tool


@tool(
    name="http_request",
    description="Make an HTTP request",
    permission="network",
    requires_approval=True,
    input_schema={"type": "object", "properties": {"url": {"type": "string"}, "method": {"type": "string"}, "headers": {"type": "object"}, "body": {"type": "object"}}, "required": ["url"]},
)
async def _http_request_async(args: dict[str, Any], context: dict[str, Any] | None = None) -> dict[str, Any]:
    import aiohttp

    url = args.get("url", "")
    method = args.get("method", "GET").upper()
    headers = args.get("headers", {})
    body = args.get("body")
    timeout = int(args.get("timeout", 30))
    if not url:
        return {"success": False, "error": "Missing 'url' argument"}
    if method not in ("GET", "POST", "PUT", "DELETE", "PATCH"):
        return {"success": False, "error": f"Unsupported method: {method}"}
    try:
        async with aiohttp.ClientSession() as session:
            kwargs: dict[str, Any] = {"headers": headers, "timeout": aiohttp.ClientTimeout(total=timeout)}
            if body and method in ("POST", "PUT", "PATCH"):
                kwargs["json"] = body
            async with session.request(method, url, **kwargs) as resp:
                text = await resp.text()
                return {
                    "success": True,
                    "status": resp.status,
                    "headers": dict(resp.headers),
                    "body": text[:10000],
                }
    except asyncio.TimeoutError:
        return {"success": False, "error": f"Request timed out after {timeout}s"}
    except Exception as e:
        return {"success": False, "error": str(e)}


http_request = _http_request_async
http_request._tool_definition = ToolDefinition(
    name="http_request",
    description="Make an HTTP request",
    handler=_http_request_async,
    permission="network",
    requires_approval=True,
    input_schema={"type": "object", "properties": {"url": {"type": "string"}}, "required": ["url"]},
)
