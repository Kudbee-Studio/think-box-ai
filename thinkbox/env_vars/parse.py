"""Fail-closed parse of env mappings against schema (PR #200)."""

from __future__ import annotations

from collections.abc import Mapping

from thinkbox.env_vars.boolean import parse_bool
from thinkbox.env_vars.errors import EnvVarsError
from thinkbox.env_vars.integer import parse_int
from thinkbox.env_vars.schema import EnvField, EnvValueKind
from thinkbox.env_vars.url import parse_url_env


def _get_raw(environ: Mapping[str, str], key: str) -> str | None:
    raw = environ.get(key)
    if raw is None:
        return None
    stripped = raw.strip()
    return stripped if stripped else None


def parse_field(field: EnvField, environ: Mapping[str, str]) -> object | None:
    raw = _get_raw(environ, field.key)
    if raw is None:
        if field.default is not None:
            raw = field.default
        elif field.required:
            raise EnvVarsError(
                error_type="MissingRequiredEnv",
                message=f"required env {field.key} is missing",
                env_key=field.key,
            )
        else:
            return None
    if field.pattern is not None and not field.pattern.search(raw):
        raise EnvVarsError(
            error_type="PatternMismatch",
            message=f"{field.key} does not match expected pattern",
            env_key=field.key,
        )
    if field.kind == EnvValueKind.STRING:
        return raw
    if field.kind == EnvValueKind.BOOL:
        return parse_bool(raw, field.key)
    if field.kind == EnvValueKind.INT:
        return parse_int(raw, field.key)
    if field.kind == EnvValueKind.URL:
        return parse_url_env(raw, field.key)
    raise EnvVarsError(
        error_type="UnknownKind",
        message=f"unknown kind for {field.key}",
        env_key=field.key,
    )


def parse_schema(
    fields: tuple[EnvField, ...],
    environ: Mapping[str, str],
) -> dict[str, object]:
    parsed: dict[str, object] = {}
    for field in fields:
        value = parse_field(field, environ)
        if value is not None:
            parsed[field.key] = value
    return parsed
