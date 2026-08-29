"""Global error handling middleware for KUDBEE API."""

from __future__ import annotations
import time
import uuid
import logging
import traceback
from typing import Any, Awaitable, Callable, Dict

from core.foundation.error_codes import ErrorCode, format_error_response
from core.foundation.errors import ThinkBoxError

logger = logging.getLogger(__name__)


def generate_request_id() -> str:
    """Generate unique request correlation ID."""
    return f"req_{uuid.uuid4().hex[:12]}"


async def error_middleware(
    request: Any,
    call_next: Callable[..., Awaitable[Any]],
) -> Any:
    """Global error boundary middleware.
    
    Catches all unhandled exceptions and returns standardized error responses.
    Injects X-Request-ID header for tracing.
    """
    request_id = generate_request_id()
    start_time = time.monotonic()

    try:
        response = await call_next(request)
        # Add tracing headers
        if hasattr(response, 'headers'):
            response.headers["X-Request-ID"] = request_id
            response.headers["X-Response-Time-Ms"] = str(round((time.monotonic() - start_time) * 1000, 2))
        return response

    except ThinkBoxError as exc:
        # Known domain errors - return structured response
        logger.warning("Domain error [%s]: %s", request_id, str(exc))
        from fastapi.responses import JSONResponse
        return JSONResponse(
            status_code=400,
            content={
                "request_id": request_id,
                "error": exc.error_type if hasattr(exc, "error_type") else "domain_error",
                "message": str(exc),
            },
            headers={"X-Request-ID": request_id},
        )

    except Exception as exc:
        # Unknown errors - log full traceback, return generic message
        logger.error(
            "Unhandled error [%s]: %s\n%s",
            request_id, str(exc), traceback.format_exc()
        )
        from fastapi.responses import JSONResponse
        return JSONResponse(
            status_code=500,
            content={
                "request_id": request_id,
                "error": ErrorCode.EXEC_FAILED.value,
                "message": "An unexpected error occurred. Reference: " + request_id,
            },
            headers={"X-Request-ID": request_id},
        )


def validate_payload_size(max_size_bytes: int = 1_000_000) -> Callable:
    """Middleware factory to enforce payload size limits."""
    async def middleware(request: Any, call_next: Callable) -> Any:
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > max_size_bytes:
            from fastapi.responses import JSONResponse
            return JSONResponse(
                status_code=413,
                content=format_error_response(
                    ErrorCode.SEC_INPUT_INVALID,
                    f"Payload exceeds {max_size_bytes} bytes limit",
                    max_size=max_size_bytes,
                ),
            )
        return await call_next(request)
    return middleware
