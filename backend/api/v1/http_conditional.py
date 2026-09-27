"""Conditional GET helpers for redacted read APIs (PR #135)."""

from __future__ import annotations

from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse, Response

from thinkbox.read_cache import (
    etag_matches,
    parse_entity_tags,
    strong_etag_from_payload,
    weak_etag_from_payload,
)


def etag_for_payload(payload: dict[str, Any], *, strong: bool = False) -> str:
    """Canonical ETag selection for control-plane read models."""
    if strong:
        return strong_etag_from_payload(payload)
    return weak_etag_from_payload(payload)


def if_match_satisfied(request: Request, etag: str) -> bool:
    """Return True when If-Match is absent or matches (allows GET-style reads)."""
    raw = request.headers.get("if-match")
    if raw is None or not str(raw).strip():
        return True
    tags = parse_entity_tags(raw)
    if "*" in tags:
        return True
    return etag_matches(raw, etag)


def precondition_failed(detail: str = "precondition_failed") -> Response:
    """412 when If-Match does not match — no silent overwrite."""
    return Response(status_code=412, content=detail)


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


def conditional_json_response_if_match(
    request: Request,
    payload: dict[str, Any],
    *,
    etag: str | None = None,
    cache_control: str = "private, max-age=0, must-revalidate",
) -> Response:
    """Like conditional_json_response but fail-closed on If-Match mismatch."""
    tag = etag or weak_etag_from_payload(payload)
    if not if_match_satisfied(request, tag):
        return precondition_failed("etag_precondition_failed")
    return conditional_json_response(
        request,
        payload,
        etag=tag,
        cache_control=cache_control,
    )
