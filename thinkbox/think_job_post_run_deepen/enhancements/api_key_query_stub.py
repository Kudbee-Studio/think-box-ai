"""API key via query param stub (F131 parity)."""

from __future__ import annotations

from typing import Any

from thinkbox.think_job_post_run_deepen.auth_stub import auth_ok


def auth_from_query(api_key: str | None) -> dict[str, Any]:
    result = auth_ok(api_key)
    result["source"] = "query"
    return result
