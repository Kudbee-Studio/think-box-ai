"""Error codes for Think Box AI operations.

Provides standardized error codes that can be used with the existing
error types in core/foundation/errors.py.
"""

from __future__ import annotations

from enum import Enum


class ErrorCode(str, Enum):
    """Standardized error codes for Think Box operations."""

    # Execution errors (1xxx)
    EXEC_EMPTY_COMMAND = "EXEC_1000"
    EXEC_TIMEOUT = "EXEC_1001"
    EXEC_COMMAND_NOT_FOUND = "EXEC_1002"
    EXEC_FAILED = "EXEC_1003"
    EXEC_UNAVAILABLE = "EXEC_1004"

    # Token errors (2xxx)
    TOKEN_NOT_FOUND = "TOKEN_2000"
    TOKEN_DUPLICATE = "TOKEN_2001"
    TOKEN_INVALID = "TOKEN_2002"

    # Challenge errors (3xxx)
    CHALLENGE_NOT_FOUND = "CHALLENGE_3000"
    CHALLENGE_INVALID_TYPE = "CHALLENGE_3001"
    CHALLENGE_INVALID_OUTCOME = "CHALLENGE_3002"

    # Box errors (4xxx)
    BOX_NOT_FOUND = "BOX_4000"
    BOX_INVALID = "BOX_4001"
    BOX_STATE_INVALID = "BOX_4002"

    # Security errors (5xxx)
    SEC_PATH_TRAVERSAL = "SEC_5000"
    SEC_ACCESS_DENIED = "SEC_5001"
    SEC_INPUT_INVALID = "SEC_5002"

    # Data errors (6xxx)
    DATA_INTEGRITY = "DATA_6000"
    DATA_VALIDATION = "DATA_6001"
    DATA_NOT_FOUND = "DATA_6002"

    # Provider errors (7xxx)
    PROVIDER_NOT_FOUND = "PROVIDER_7000"
    PROVIDER_UNAVAILABLE = "PROVIDER_7001"
    PROVIDER_TIMEOUT = "PROVIDER_7002"


def error_dict(code: ErrorCode, message: str, **kwargs: any) -> dict:
    """Create a standardized error response dict."""
    return {
        "error": code.value,
        "message": message,
        "details": kwargs,
    }