"""Rate-limit decision stub (hermetic, no HTTP)."""

from __future__ import annotations

from typing import Any


def rate_limit_allow(request_count: int, limit: int = 32) -> dict[str, Any]:
    allowed = request_count <= limit
    return {
        "allowed": allowed,
        "request_count": request_count,
        "limit": limit,
        "live_api_called": False,
    }
