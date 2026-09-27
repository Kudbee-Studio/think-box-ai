"""Detect secret-shaped values in errors (PR #200)."""

from __future__ import annotations

import re

from thinkbox.env_vars.redact import looks_sensitive_key, redact_string_value

_LONG_TOKEN_RE = re.compile(r"[A-Za-z0-9_-]{32,}")


def sanitize_error_message(message: str, env_key: str | None = None) -> str:
    out = redact_string_value(message)
    if env_key and looks_sensitive_key(env_key):
        return "[REDACTED_ERROR]"
    if _LONG_TOKEN_RE.search(out):
        return _LONG_TOKEN_RE.sub("[REDACTED_TOKEN]", out)
    return out
