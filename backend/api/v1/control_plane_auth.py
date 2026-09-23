"""Control-plane API auth — fail-closed (PR #154)."""

from __future__ import annotations

import os

from fastapi import Header, HTTPException

LOCAL_DEV_TOKEN = "dev-only-local-token"
CONTROL_PLANE_TOKEN_ENV = "THINKBOX_CONTROL_PLANE_TOKEN"

__all__ = (
    "CONTROL_PLANE_TOKEN_ENV",
    "LOCAL_DEV_TOKEN",
    "configured_control_plane_token",
    "require_control_plane_auth",
)


def configured_control_plane_token() -> str | None:
    """Return configured bearer secret, if any."""
    explicit = os.environ.get(CONTROL_PLANE_TOKEN_ENV)
    if explicit:
        return explicit.strip()
    if os.environ.get("THINKBOX_CONTROL_PLANE_ALLOW_DEV_TOKEN", "").lower() in (
        "1",
        "true",
        "yes",
    ):
        return LOCAL_DEV_TOKEN
    return None


def require_control_plane_auth(authorization: str | None = Header(None)) -> str:
    """Fail-closed: missing or wrong bearer → 401."""
    expected = configured_control_plane_token()
    if not expected:
        raise HTTPException(
            status_code=503,
            detail="control_plane_unconfigured: set THINKBOX_CONTROL_PLANE_TOKEN",
        )
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Unauthorized: Bearer token required")
    token = authorization.removeprefix("Bearer ").strip()
    if token != expected:
        raise HTTPException(status_code=401, detail="Unauthorized: invalid token")
    return token
