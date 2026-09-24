"""URL env validation (PR #200)."""

from __future__ import annotations

from urllib.parse import urlparse

from thinkbox.env_vars.errors import EnvVarsError

_LOOPBACK = frozenset({"127.0.0.1", "localhost", "::1"})


def parse_url_env(raw: str, key: str, require_https: bool = False) -> str:
    stripped = raw.strip()
    if not stripped:
        raise EnvVarsError(error_type="EmptyUrlEnv", message=f"{key} is empty", env_key=key)
    parsed = urlparse(stripped)
    if not parsed.scheme or not parsed.netloc:
        raise EnvVarsError(
            error_type="InvalidUrlEnv",
            message=f"{key} is not a valid URL",
            env_key=key,
        )
    if require_https and parsed.scheme.lower() != "https":
        raise EnvVarsError(
            error_type="HttpsRequired",
            message=f"{key} must use https",
            env_key=key,
        )
    return stripped


def is_loopback_url(url: str) -> bool:
    host = (urlparse(url).hostname or "").lower()
    return host in _LOOPBACK or host.endswith(".localhost")
