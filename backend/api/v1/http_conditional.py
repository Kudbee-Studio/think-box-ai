"""Conditional GET helpers for redacted read APIs (PR #135)."""

from __future__ import annotations

from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse, Response

from thinkbox.read_cache import etag_matches, weak_etag_from_payload


def conditional_json_response(
    request: Request,
    payload: dict[str, Any],
    *,
    etag: str | None = None,
    cache_control: str = "private, max-age=0, must-revalidate",
) -> Response:
    """Return 304 when If-None-Match matches the payload ETag."""
    tag = etag or weak_etag_from_payload(payload)
    inm = request.headers.get("if-none-match")
    if etag_matches(inm, tag):
        return Response(
            status_code=304,
            headers={"ETag": tag, "Cache-Control": cache_control},
        )
    return JSONResponse(
        content=payload,
        headers={"ETag": tag, "Cache-Control": cache_control},
    )
