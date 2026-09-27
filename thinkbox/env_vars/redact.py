"""Redact secret-shaped env values for logs and receipts (PR #200)."""

from __future__ import annotations

import re
from typing import Any

from thinkbox.org_memory_receipts import redact_mapping as _org_redact

_SECRET_KEY_PARTS = frozenset(
    {
        "token",
        "api_key",
        "apikey",
        "password",
        "secret",
        "authorization",
        "bearer",
        "private",
    },
)
_SK_RE = re.compile(r"sk-[A-Za-z0-9]{8,}", re.IGNORECASE)
_TB_KEY_RE = re.compile(r"tb_[A-Za-z0-9_-]{8,}", re.IGNORECASE)


def looks_sensitive_key(key: str) -> bool:
    key_l = key.lower()
    return any(part in key_l for part in _SECRET_KEY_PARTS)


def redact_string_value(value: str) -> str:
    if not value:
        return value
    out = _SK_RE.sub("sk-[REDACTED]", value)
    return _TB_KEY_RE.sub("tb_[REDACTED]", out)


def redact_environ_for_display(environ: dict[str, str]) -> dict[str, str]:
    out: dict[str, str] = {}
    for key, val in sorted(environ.items()):
        if looks_sensitive_key(key):
            out[key] = "[REDACTED]" if val else "[EMPTY]"
        else:
            out[key] = redact_string_value(val) if val else "[EMPTY]"
    return out


def redact_nested(data: dict[str, Any]) -> dict[str, Any]:
    return _org_redact(data)
