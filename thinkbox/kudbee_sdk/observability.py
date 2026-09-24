"""Correlation IDs and redacted log lines (PR #177 F18)."""

from __future__ import annotations

import uuid
from typing import Any

from thinkbox.kudbee_sdk.config import KudbeeSdkConfig
from thinkbox.kudbee_sdk.redact import redact_mapping, redact_string


def new_correlation_id() -> str:
    return f"kudbee-{uuid.uuid4().hex[:16]}"


def correlation_headers(config: KudbeeSdkConfig, correlation_id: str | None) -> dict[str, str]:
    cid = correlation_id or new_correlation_id()
    return {config.correlation_header: cid, "accept": "application/json"}


def format_log_line(event: str, fields: dict[str, Any]) -> str:
    safe = redact_mapping({k: (v if isinstance(v, (int, float, bool)) else str(v)) for k, v in fields.items()})
    parts = " ".join(f"{k}={redact_string(str(v))}" for k, v in safe.items())
    return f"event={event} {parts}".strip()
