"""Security hardening for KUDBEE API endpoints."""

from __future__ import annotations
import os
from typing import Any

from core.foundation.error_codes import ErrorCode, format_error_response


# Explicit CORS whitelist - never use ["*"] in production
ALLOWED_ORIGINS: set[str] = {
    "http://localhost:3000",
    "http://localhost:3001",
    "http://localhost:5173",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:3001",
}

# Add production origins from env
_env_origins = os.environ.get("ALLOWED_ORIGINS", "")
if _env_origins:
    ALLOWED_ORIGINS.update(_env_origins.split(","))


def get_cors_config() -> dict[str, Any]:
    """Return CORS middleware configuration."""
    return {
        "allow_origins": list(ALLOWED_ORIGINS),
        "allow_credentials": True,
        "allow_methods": ["GET", "POST", "DELETE", "OPTIONS"],
        "allow_headers": ["Content-Type", "X-API-Key", "X-Request-ID"],
    }


def validate_origin(origin: str | None) -> bool:
    """Check if origin is in whitelist."""
    if not origin:
        return False
    return origin in ALLOWED_ORIGINS


# Payload limits per endpoint
PAYLOAD_LIMITS: dict[str, int] = {
    "default": 1_000_000,      # 1MB
    "/api/chat": 5_000_000,    # 5MB for chat (long context)
    "/api/boxes": 100_000,     # 100KB for box CRUD
}


def get_payload_limit(path: str) -> int:
    """Get max payload size for endpoint."""
    for endpoint, limit in PAYLOAD_LIMITS.items():
        if path.startswith(endpoint):
            return limit
    return PAYLOAD_LIMITS["default"]
