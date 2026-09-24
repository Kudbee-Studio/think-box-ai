"""Boolean env parsing, fail-closed (PR #200)."""

from __future__ import annotations

from thinkbox.env_vars.errors import EnvVarsError

_TRUTHY = frozenset({"1", "true", "yes", "on", "ack"})
_FALSY = frozenset({"0", "false", "no", "off"})


def parse_bool(raw: str, key: str) -> bool:
    stripped = raw.strip()
    lowered = stripped.lower()
    if lowered in _TRUTHY:
        return True
    if lowered in _FALSY:
        return False
    raise EnvVarsError(
        error_type="InvalidBoolEnv",
        message=f"cannot parse boolean for {key}",
        env_key=key,
        context={"value_length": len(stripped)},
    )
