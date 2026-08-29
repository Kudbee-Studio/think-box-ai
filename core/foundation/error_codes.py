"""Standardized error codes for KUDBEE system boundary."""

from __future__ import annotations
from enum import Enum
from typing import Any, Dict


class ErrorCode(str, Enum):
    """Standardized error codes across the KUDBEE system boundary."""
    
    # Execution Domain (1xxx)
    EXEC_EMPTY_COMMAND = "EXEC_1000"
    EXEC_TIMEOUT = "EXEC_1001"
    EXEC_COMMAND_NOT_FOUND = "EXEC_1002"
    EXEC_FAILED = "EXEC_1003"
    EXEC_UNAVAILABLE = "EXEC_1004"
    
    # Token Domain (2xxx)
    TOKEN_NOT_FOUND = "TOKEN_2000"
    TOKEN_DUPLICATE = "TOKEN_2001"
    TOKEN_INVALID = "TOKEN_2002"
    
    # Challenge Domain (3xxx)
    CHALLENGE_NOT_FOUND = "CHALLENGE_3000"
    CHALLENGE_INVALID_TYPE = "CHALLENGE_3001"
    CHALLENGE_INVALID_OUTCOME = "CHALLENGE_3002"
    
    # Box Domain (4xxx)
    BOX_NOT_FOUND = "BOX_4000"
    BOX_INVALID = "BOX_4001"
    BOX_STATE_INVALID = "BOX_4002"
    
    # Security Domain (5xxx)
    SEC_PATH_TRAVERSAL = "SEC_5000"
    SEC_ACCESS_DENIED = "SEC_5001"
    SEC_INPUT_INVALID = "SEC_5002"
    
    # Data Domain (6xxx)
    DATA_INTEGRITY = "DATA_6000"
    DATA_VALIDATION = "DATA_6001"
    DATA_NOT_FOUND = "DATA_6002"
    
    # Provider Domain (7xxx)
    PROVIDER_NOT_FOUND = "PROVIDER_7000"
    PROVIDER_UNAVAILABLE = "PROVIDER_7001"
    PROVIDER_TIMEOUT = "PROVIDER_7002"
    PROVIDER_AUTH = "PROVIDER_7003"
    PROVIDER_PAYMENT = "PROVIDER_7004"
    PROVIDER_RATE_LIMIT = "PROVIDER_7005"


def format_error_response(code: ErrorCode, message: str, **details: Any) -> Dict[str, Any]:
    """Generates an immutable error payload schema.
    
    Time Complexity: O(1)
    Space Complexity: O(1)
    """
    return {
        "error_code": code.value,
        "message": message,
        "details": details,
    }
