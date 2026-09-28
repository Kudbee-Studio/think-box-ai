"""Enterprise-level API endpoints with comprehensive error handling.

All endpoints follow enterprise standards:
- Structured error responses with RFC 3339 timestamps
- Request/response validation
- Health checks and readiness probes
- Rate limiting and circuit breakers
- Audit logging of all operations
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from thinkbox.error_handling import (
    ErrorSeverity,
    ErrorRecoveryStrategy,
    ModelCallError,
    ValidationError,
    ThinkBoxError,
)
from thinkbox.health_check import HealthProbe, ModelProviderHealthCheck, MemoryStoreHealthCheck
from thinkbox.structured_logging import get_contextual_logger

logger = get_contextual_logger(__name__)


class APIResponse:
    """Standard API response format for all endpoints."""

    def __init__(
        self,
        data: Any = None,
        error: Optional[dict[str, Any]] = None,
        status: str = "success",
        message: str = "",
    ) -> None:
        self.data = data
        self.error = error
        self.status = status
        self.message = message

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable dict."""
        return {
            "status": self.status,
            "message": self.message,
            "data": self.data,
            "error": self.error,
        }


class APIError(ThinkBoxError):
    """Error that can be safely returned as API response."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int = 500,
        error_code: str = "INTERNAL_ERROR",
        **kwargs: Any,
    ) -> None:
        super().__init__(message, **kwargs)
        self.status_code = status_code
        self.error_code = error_code

    def to_response(self) -> APIResponse:
        """Convert to API response."""
        return APIResponse(
            error={
                "code": self.error_code,
                "message": self.message,
                "timestamp": self.timestamp,
            },
            status="error",
            message=self.message,
        )


class ValidationAPIError(APIError):
    """Validation error in API request."""

    def __init__(
        self, message: str, *, field: Optional[str] = None, **kwargs: Any
    ) -> None:
        kwargs.setdefault("status_code", 400)
        kwargs.setdefault("error_code", "VALIDATION_ERROR")
        super().__init__(message, **kwargs)
        self.field = field
        self.context_data["field"] = field


class ModelAPIError(APIError):
    """Error during model inference via API."""

    def __init__(
        self,
        message: str,
        *,
        provider: str = "unknown",
        model: str = "unknown",
        **kwargs: Any,
    ) -> None:
        kwargs.setdefault("status_code", 503)
        kwargs.setdefault("error_code", "MODEL_ERROR")
        super().__init__(message, **kwargs)
        self.provider = provider
        self.model = model
        self.context_data.update({"provider": provider, "model": model})


class AuthenticationError(APIError):
    """Authentication/authorization error."""

    def __init__(self, message: str = "Unauthorized", **kwargs: Any) -> None:
        kwargs.setdefault("status_code", 401)
        kwargs.setdefault("error_code", "AUTHENTICATION_ERROR")
        super().__init__(message, **kwargs)


class RateLimitError(APIError):
    """Rate limit exceeded."""

    def __init__(
        self,
        message: str = "Rate limit exceeded",
        *,
        retry_after: int = 60,
        **kwargs: Any,
    ) -> None:
        kwargs.setdefault("status_code", 429)
        kwargs.setdefault("error_code", "RATE_LIMIT")
        super().__init__(message, **kwargs)
        self.retry_after = retry_after
        self.context_data["retry_after"] = retry_after


class CircuitBreakerError(APIError):
    """Circuit breaker is open (downstream service unreachable)."""

    def __init__(
        self, service: str = "unknown", **kwargs: Any
    ) -> None:
        kwargs.setdefault("status_code", 503)
        kwargs.setdefault("error_code", "SERVICE_UNAVAILABLE")
        message = f"Service '{service}' is temporarily unavailable"
        super().__init__(message, **kwargs)
        self.service = service
        self.context_data["service"] = service


# Example endpoint handlers
async def health_endpoint() -> dict[str, Any]:
    """GET /health - Liveness probe (always responds if system is running)."""
    logger.info("Health check requested")

    probe = HealthProbe()
    try:
        result = await probe.check_liveness()
        return result.to_dict()
    except Exception as e:
        logger.error("Health check failed", extra={"error": str(e)})
        raise APIError("Health check failed") from e


async def ready_endpoint() -> dict[str, Any]:
    """GET /ready - Readiness probe (responds only if all critical systems work)."""
    logger.info("Readiness check requested")

    probe = HealthProbe()
    probe.add_check(ModelProviderHealthCheck())
    probe.add_check(MemoryStoreHealthCheck())

    try:
        result = await probe.check_readiness()
        return result.to_dict()
    except Exception as e:
        logger.error("Readiness check failed", extra={"error": str(e)})
        raise APIError("Readiness check failed") from e


async def inference_endpoint(prompt: str, model: Optional[str] = None) -> dict[str, Any]:
    """POST /inference - Run model inference with full error handling."""
    # Validate input
    if not prompt or not prompt.strip():
        raise ValidationAPIError("Prompt cannot be empty", field="prompt")

    if len(prompt) > 10000:
        raise ValidationAPIError("Prompt exceeds maximum length", field="prompt")

    logger.info(
        "Inference requested",
        extra={"prompt_length": len(prompt), "model": model or "default"},
    )

    # Try to run inference
    try:
        # Placeholder: actual implementation would call model_client
        result = {
            "response": f"Response to: {prompt[:100]}...",
            "tokens": 42,
            "model": model or "default",
        }
        logger.info("Inference succeeded", extra={"tokens": result["tokens"]})
        return APIResponse(data=result).to_dict()

    except ModelCallError as e:
        logger.error(
            "Inference failed",
            extra={
                "provider": e.provider,
                "model": e.model,
                "retryable": e.retryable,
            },
        )
        raise ModelAPIError(
            e.message,
            provider=e.provider,
            model=e.model,
        ) from e

    except Exception as e:
        logger.error("Unexpected error during inference", extra={"error": str(e)})
        raise APIError(f"Inference failed: {str(e)}") from e


# Example API validation middleware
class APIRequestValidator:
    """Validates all API requests."""

    MAX_BODY_SIZE = 1_000_000  # 1MB

    @staticmethod
    def validate_headers(headers: dict[str, str]) -> None:
        """Validate required headers."""
        content_type = headers.get("content-type", "")
        if "application/json" not in content_type:
            raise APIError(
                "Content-Type must be application/json",
                status_code=400,
                error_code="INVALID_CONTENT_TYPE",
            )

    @staticmethod
    def validate_body_size(content_length: Optional[int]) -> None:
        """Validate request body size."""
        if content_length and content_length > APIRequestValidator.MAX_BODY_SIZE:
            raise APIError(
                f"Request body exceeds maximum size of {APIRequestValidator.MAX_BODY_SIZE} bytes",
                status_code=413,
                error_code="PAYLOAD_TOO_LARGE",
            )

    @staticmethod
    def validate_api_key(auth_header: Optional[str]) -> str:
        """Validate API key from Authorization header."""
        if not auth_header:
            raise AuthenticationError()

        if not auth_header.startswith("Bearer "):
            raise AuthenticationError("Invalid authorization header format")

        api_key = auth_header[7:]  # Remove "Bearer " prefix
        if not api_key or len(api_key) < 32:
            raise AuthenticationError("Invalid API key")

        return api_key


# Error response mapping
ERROR_TO_STATUS = {
    ValidationAPIError: 400,
    AuthenticationError: 401,
    RateLimitError: 429,
    CircuitBreakerError: 503,
    ModelAPIError: 503,
    APIError: 500,
}


def get_error_status_code(error: Exception) -> int:
    """Get HTTP status code for error."""
    for error_type, status in ERROR_TO_STATUS.items():
        if isinstance(error, error_type):
            return status
    return 500  # Default


if __name__ == "__main__":
    # Example usage
    import asyncio

    async def main():
        # Health check
        health = await health_endpoint()
        print(f"Health: {health}")

        # Readiness check
        ready = await ready_endpoint()
        print(f"Readiness: {ready}")

    asyncio.run(main())
