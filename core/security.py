"""Security hardening for Think Box AI."""

from __future__ import annotations

import hashlib
import hmac
import secrets
import time
from functools import wraps
from typing import Any

from core.foundation.logging import get_logger

logger = get_logger(__name__)


def generate_api_key() -> str:
    """Generate a secure API key."""
    return f"tb_{secrets.token_hex(32)}"


def hash_api_key(key: str) -> str:
    """Hash an API key for storage."""
    return hashlib.sha256(key.encode()).hexdigest()


def verify_api_key(key: str, hashed: str) -> bool:
    """Verify an API key against its hash."""
    return hmac.compare_digest(hash_api_key(key), hashed)


def rate_limit(requests_per_minute: int = 60):
    """Decorator for rate limiting."""
    _requests: dict[str, list[float]] = {}

    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Extract client IP from request
            request = next((a for a in args if hasattr(a, "client")), None)
            client = request.client.host if request and request.client else "unknown"
            now = time.time()

            if client not in _requests:
                _requests[client] = []
            _requests[client] = [t for t in _requests[client] if now - t < 60]

            if len(_requests[client]) >= requests_per_minute:
                from fastapi import HTTPException
                raise HTTPException(429, "Rate limit exceeded")

            _requests[client].append(now)
            return await func(*args, **kwargs)
        return wrapper
    return decorator


# CSP Header
CSP_HEADER = (
    "default-src 'self'; "
    "script-src 'self' 'unsafe-inline'; "
    "style-src 'self' 'unsafe-inline'; "
    "img-src 'self' data: https:; "
    "font-src 'self'; "
    "connect-src 'self' ws: wss:; "
    "frame-ancestors 'none'; "
    "base-uri 'self'; "
    "form-action 'self'"
)


def security_headers() -> dict[str, str]:
    """Get recommended security headers."""
    return {
        "Content-Security-Policy": CSP_HEADER,
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
        "X-XSS-Protection": "1; mode=block",
        "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
        "Referrer-Policy": "strict-origin-when-cross-origin",
        "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
    }
