"""HTTP tool for THINK BOX AI — GET only, rate-limited, saves raw responses."""

from __future__ import annotations

import asyncio
import hashlib
import json
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from core.tools.registry import tool

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_RAW_DIR = _REPO_ROOT / "data" / "raw"

_rate_limits: dict[str, float] = {}
_MIN_INTERVAL = 0.4  # 400ms between requests to same host
_TIMEOUT = 20
_USER_AGENT = "ThinkBoxAI-Research/0.2 (+https://github.com/Kudbee-Studio/think-box-ai)"


async def _rate_limit(host: str) -> None:
    now = time.monotonic()
    last = _rate_limits.get(host, 0.0)
    wait = _MIN_INTERVAL - (now - last)
    if wait > 0:
        await asyncio.sleep(wait)
    _rate_limits[host] = time.monotonic()


def _safe_filename(url: str) -> str:
    h = hashlib.sha256(url.encode()).hexdigest()[:16]
    return h


@tool(
    name="http_get",
    description="HTTP GET with rate limiting. Saves JSON responses to data/raw/. Returns status, excerpt, and saved path.",
    permission="network",
    input_schema={"type": "object", "properties": {"url": {"type": "string"}, "save": {"type": "boolean"}}, "required": ["url"]},
)
async def http_get(args: dict[str, Any], context: dict[str, Any] | None = None) -> dict[str, Any]:
    url = args.get("url", "")
    save = args.get("save", True)
    if not url:
        return {"success": False, "error": "Missing 'url' argument"}

    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        return {"success": False, "error": f"Unsupported scheme: {parsed.scheme}"}
    host = parsed.netloc

    await _rate_limit(host)

    try:
        import urllib.request
        import urllib.error

        req = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT, "Accept": "application/json, text/plain, */*"})
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
            status = resp.status
            content_type = resp.headers.get("Content-Type", "")
            body = resp.read()

        saved_path = None
        if save:
            host_dir = _RAW_DIR / host.replace(":", "_")
            host_dir.mkdir(parents=True, exist_ok=True)
            is_json = "json" in content_type or url.endswith(".json")
            ext = "json" if is_json else "txt"
            fname = f"{_safe_filename(url)}.{ext}"
            saved_path = str(host_dir.relative_to(_REPO_ROOT) / fname)
            (host_dir / fname).write_bytes(body)

        text = body.decode("utf-8", errors="replace")
        try:
            parsed_json = json.loads(text) if is_json else None
        except json.JSONDecodeError:
            parsed_json = None

        excerpt = text[:2000] if len(text) > 2000 else text

        return {
            "success": True,
            "status": status,
            "url": url,
            "content_type": content_type,
            "saved_path": saved_path,
            "excerpt": excerpt,
            "json": parsed_json,
            "size": len(body),
        }
    except urllib.error.HTTPError as e:
        return {"success": False, "error": f"HTTP {e.code}: {e.reason}", "url": url}
    except urllib.error.URLError as e:
        return {"success": False, "error": f"URL error: {e.reason}", "url": url}
    except Exception as e:
        return {"success": False, "error": str(e), "url": url}
