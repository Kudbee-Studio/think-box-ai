"""Security middleware for Think Box AI backend."""

from __future__ import annotations

import hashlib
import hmac
import os
import sys
import time
from collections import defaultdict
from typing import Any

from fastapi import Request, Response
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

ALLOWED_ORIGINS = os.environ.get(
    "THINKBOX_ALLOWED_ORIGINS",
    "http://localhost:3000,http://localhost:8080,http://localhost:5173",
).split(",")

API_KEY_HEADER = "X-API-Key"
RATE_LIMIT_WINDOW = 60
RATE_LIMIT_MAX_REQUESTS = int(os.environ.get("THINKBOX_RATE_LIMIT", "100"))
MAX_REQUEST_BODY_SIZE = 1_048_576

DEFAULT_API_KEYS = {"changeme-production-key", "changeme", "test", "admin", "password"}


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Any) -> Response:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["Content-Security-Policy"] = "default-src 'self'"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
        response.headers.pop("Server", None)
        return response


class AuthenticationMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: Any, api_keys: set[str] | None = None):
        super().__init__(app)
        self._api_keys = api_keys or set()
        self._exempt_paths = {"/health", "/docs", "/openapi.json", "/favicon.ico"}

    def _is_exempt(self, path: str) -> bool:
        return path in self._exempt_paths

    def _validate_key(self, request: Request) -> bool:
        key = request.headers.get(API_KEY_HEADER, "")
        if not key:
            key = request.query_params.get("api_key", "")
        if not key:
            return False
        for valid_key in self._api_keys:
            if hmac.compare_digest(key, valid_key):
                return True
        return False

    async def dispatch(self, request: Request, call_next: Any) -> Response:
        if self._is_exempt(request.url.path):
            return await call_next(request)

        if self._api_keys and not self._validate_key(request):
            return Response(
                content='{"error": "Unauthorized", "message": "Valid API key required"}',
                status_code=401,
                media_type="application/json",
            )

        return await call_next(request)


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: Any, max_requests: int = RATE_LIMIT_MAX_REQUESTS, window: int = RATE_LIMIT_WINDOW):
        super().__init__(app)
        self._max_requests = max_requests
        self._window = window
        self._requests: dict[str, list[float]] = defaultdict(list)

    def _client_ip(self, request: Request) -> str:
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
        if request.client:
            return request.client.host
        return "unknown"

    def _is_rate_limited(self, client_ip: str) -> bool:
        now = time.time()
        window_start = now - self._window
        self._requests[client_ip] = [
            t for t in self._requests[client_ip] if t > window_start
        ]
        if len(self._requests[client_ip]) >= self._max_requests:
            return True
        self._requests[client_ip].append(now)
        return False

    async def dispatch(self, request: Request, call_next: Any) -> Response:
        client_ip = self._client_ip(request)

        if self._is_rate_limited(client_ip):
            return Response(
                content='{"error": "Rate limit exceeded", "retry_after": 60}',
                status_code=429,
                media_type="application/json",
                headers={"Retry-After": str(self._window)},
            )

        response = await call_next(request)
        remaining = max(0, self._max_requests - len(self._requests[client_ip]))
        response.headers["X-RateLimit-Limit"] = str(self._max_requests)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        response.headers["X-RateLimit-Window"] = str(self._window)
        return response


class RequestSizeLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: Any, max_size: int = MAX_REQUEST_BODY_SIZE):
        super().__init__(app)
        self._max_size = max_size

    async def dispatch(self, request: Request, call_next: Any) -> Response:
        if request.method in ("POST", "PUT", "PATCH"):
            body = await request.body()
            if len(body) > self._max_size:
                return Response(
                    content=f'{{"error": "Request too large", "max_size": {self._max_size}}}',
                    status_code=413,
                    media_type="application/json",
                )
        return await call_next(request)


def get_api_keys() -> set[str]:
    keys_env = os.environ.get("THINKBOX_API_KEYS", "")
    if not keys_env:
        default_key = os.environ.get("THINKBOX_API_KEY", "")
        if default_key and default_key not in DEFAULT_API_KEYS:
            return {default_key}
        return set()
    keys = set(k.strip() for k in keys_env.split(",") if k.strip())
    return {k for k in keys if k not in DEFAULT_API_KEYS}


def validate_api_keys_or_exit() -> set[str]:
    keys = get_api_keys()
    if not keys:
        print(
            "FATAL: THINKBOX_API_KEY or THINKBOX_API_KEYS environment variable must be set.\n"
            "Generate a secure key: python3 -c \"import secrets; print('tb_' + secrets.token_urlsafe(32))\"\n"
            "Set it with: export THINKBOX_API_KEY=your_key_here",
            file=sys.stderr,
        )
        sys.exit(1)
    return keys


def validate_ws_token(query_params: dict[str, str], headers: dict[str, str], valid_keys: set[str]) -> bool:
    token = headers.get(API_KEY_HEADER, "")
    if not token:
        token = query_params.get("token", "")
    if not token:
        token = query_params.get("api_key", "")
    if not token:
        return False
    for valid_key in valid_keys:
        if hmac.compare_digest(token, valid_key):
            return True
    return False


def setup_cors(app: Any) -> None:
    origins = [o.strip() for o in ALLOWED_ORIGINS if o.strip()]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "DELETE"],
        allow_headers=["Authorization", "Content-Type", "X-API-Key"],
    )


def setup_security(app: Any) -> None:
    api_keys = get_api_keys()
    setup_cors(app)
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(AuthenticationMiddleware, api_keys=api_keys)
    app.add_middleware(RateLimitMiddleware)
    app.add_middleware(RequestSizeLimitMiddleware)
