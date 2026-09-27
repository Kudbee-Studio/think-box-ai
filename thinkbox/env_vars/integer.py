"""Integer env parsing, fail-closed (PR #200)."""

from __future__ import annotations

from thinkbox.env_vars.errors import EnvVarsError


def parse_int(raw: str, key: str, min_value: int | None = None, max_value: int | None = None) -> int:
    stripped = raw.strip()
    try:
        value = int(stripped, 10)
    except ValueError:
        raise EnvVarsError(
            error_type="InvalidIntEnv",
            message=f"cannot parse integer for {key}",
            env_key=key,
        ) from None
    if min_value is not None and value < min_value:
        raise EnvVarsError(
            error_type="IntBelowMin",
            message=f"{key} below minimum {min_value}",
            env_key=key,
            context={"min": min_value, "actual": value},
        )
    if max_value is not None and value > max_value:
        raise EnvVarsError(
            error_type="IntAboveMax",
            message=f"{key} above maximum {max_value}",
            env_key=key,
            context={"max": max_value, "actual": value},
        )
    return value
